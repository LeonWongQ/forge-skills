"""Independent user-global learning Hook registration for supported hosts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .data_paths import forge_data_root
from .learning_collector import _REGISTRY_LOCK, _registry_file_lock
from .learning_hook_providers import (
    SUPPORTED_HOSTS,
    LearningHookProvider,
    build_hook_commands,
    provider_for,
)
from .personal_hook_state import _atomic_write, _json_bytes


STATE_VERSION = "3.0"
LEGACY_STATE_VERSIONS = {"1.0", "2.0"}
HOOK_EVENT_STALE_HOURS = 24


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hook_state_path(forge_root: Path) -> Path:
    return forge_data_root(forge_root) / "learning-hooks.json"


def hook_event_status_path(forge_root: Path, host: str) -> Path:
    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported Hook host: {host}")
    return forge_data_root(forge_root) / "hook-status" / f"{host}.json"


def load_hook_state(forge_root: Path) -> dict[str, Any]:
    path = hook_state_path(forge_root)
    if not path.is_file():
        return {"schemaVersion": STATE_VERSION, "hosts": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read learning Hook state: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid learning Hook state: {path}")
    hosts = value.get("hosts")
    if not isinstance(hosts, dict):
        raise ValueError(f"invalid learning Hook state: {path}")
    version = value.get("schemaVersion")
    if version == "1.0":
        projects = value.get("projects")
        if not isinstance(projects, dict):
            raise ValueError(f"invalid legacy learning Hook state: {path}")
    if version not in {*LEGACY_STATE_VERSIONS, STATE_VERSION}:
        raise ValueError(f"unsupported learning Hook state: {path}")
    legacy_selected = value.get("selectedHost") if version == "2.0" else None
    if legacy_selected is not None and legacy_selected not in SUPPORTED_HOSTS:
        raise ValueError(f"invalid selected Hook host: {path}")
    invalid_hosts = set(hosts) - set(SUPPORTED_HOSTS)
    if invalid_hosts:
        raise ValueError(f"invalid learning Hook hosts: {path}")
    return {"schemaVersion": STATE_VERSION, "hosts": hosts}


def _save_hook_state(forge_root: Path, state: dict[str, Any]) -> None:
    _atomic_write(hook_state_path(forge_root), _json_bytes(state))


def _skill_root(forge_root: Path) -> Path:
    base = forge_root.parent if forge_root.name == "forge" else forge_root
    return base / "skills" / "learning-collector"


def _runtime(forge_root: Path) -> tuple[Path, Path, Path]:
    path = forge_data_root(forge_root) / "runtime.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read Forge runtime configuration: {path}") from error
    executable = value.get("pythonExecutable") if isinstance(value, dict) else None
    timeout = value.get("directCollectionTimeoutSeconds") if isinstance(value, dict) else None
    if not isinstance(executable, str) or not executable.strip():
        raise ValueError("Forge runtime pythonExecutable is not configured")
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("Forge runtime directCollectionTimeoutSeconds must be a positive integer")
    installation = value.get("hookInstallationRoot") if isinstance(value, dict) else None
    if installation is not None and (not isinstance(installation, str) or not installation.strip()):
        raise ValueError("Forge runtime hookInstallationRoot must be a non-empty string")
    if isinstance(installation, str):
        installation_root = Path(installation).expanduser().absolute()
        hook_forge_root = installation_root / "forge"
        hook_skill_root = installation_root / "skills" / "learning-collector"
        try:
            same_forge = hook_forge_root.resolve() == forge_root.resolve()
            same_skill = hook_skill_root.resolve() == _skill_root(forge_root).resolve()
        except OSError as error:
            raise ValueError("Forge Hook installation root is unavailable") from error
        if not same_forge or not same_skill:
            raise ValueError(
                "Forge runtime hookInstallationRoot does not point to this Forge installation"
            )
    else:
        hook_forge_root = forge_root.absolute()
        hook_skill_root = _skill_root(forge_root).absolute()
    return Path(executable), hook_forge_root, hook_skill_root


def _current_commands(forge_root: Path, host: str) -> dict[str, str]:
    executable, hook_forge_root, hook_skill_root = _runtime(forge_root)
    script = hook_skill_root / "scripts" / "host_capture_hook.py"
    return build_hook_commands(
        executable, script, host, forge_root=hook_forge_root
    )


def _provider_from_record(
    host: str,
    record: dict[str, Any] | None,
    forge_root: Path,
    *,
    home: Path | None,
    codex_home: Path | None,
) -> tuple[LearningHookProvider, dict[str, str]]:
    commands = record.get("commands") if isinstance(record, dict) else None
    if not isinstance(commands, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in commands.items()
    ):
        commands = _current_commands(forge_root, host)
    if isinstance(record, dict) and isinstance(record.get("configPath"), str):
        return LearningHookProvider(host, Path(record["configPath"]), commands), commands
    return provider_for(host, commands, home=home, codex_home=codex_home), commands


def _current_provider(
    forge_root: Path,
    host: str,
    *,
    home: Path | None,
    codex_home: Path | None,
) -> tuple[LearningHookProvider, dict[str, str]]:
    commands = _current_commands(forge_root, host)
    return provider_for(host, commands, home=home, codex_home=codex_home), commands


def _same_provider(left: LearningHookProvider, right: LearningHookProvider) -> bool:
    return left.config_path == right.config_path and left.commands == right.commands


def _load_last_event(forge_root: Path, host: str) -> dict[str, Any] | None:
    try:
        value = json.loads(hook_event_status_path(forge_root, host).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) and value.get("host") == host else None


def _runtime_state(event: dict[str, Any] | None, installed_at: Any = None) -> str:
    if event is None:
        return "NEVER_OBSERVED"
    if event.get("outcome") == "FAILED":
        return "ERROR"
    timestamp = event.get("timestamp")
    try:
        observed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return "ERROR"
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    try:
        installed = datetime.fromisoformat(str(installed_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        installed = None
    if installed is not None:
        if installed.tzinfo is None:
            installed = installed.replace(tzinfo=timezone.utc)
        if observed_at < installed:
            return "NEVER_OBSERVED"
    return (
        "STALE"
        if datetime.now(timezone.utc) - observed_at > timedelta(hours=HOOK_EVENT_STALE_HOURS)
        else "HEALTHY"
    )


def _event_scope(
    event: dict[str, Any] | None,
    *,
    configured: bool,
    installed_at: Any,
) -> str:
    """Classify a receipt without presenting historical evidence as current."""
    if event is None:
        return "NONE"
    if not configured or not isinstance(installed_at, str):
        return "HISTORICAL"
    try:
        observed = datetime.fromisoformat(str(event.get("timestamp")).replace("Z", "+00:00"))
        installed = datetime.fromisoformat(installed_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "UNKNOWN"
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    if installed.tzinfo is None:
        installed = installed.replace(tzinfo=timezone.utc)
    return "CURRENT_INSTALLATION" if observed >= installed else "HISTORICAL"


def _native_capability_status(host: str, configured: bool) -> tuple[str, str]:
    """Report only trust/enable facts this generic manager can establish."""
    if not configured:
        return "NOT_APPLICABLE", "NOT_APPLICABLE"
    trust = "MANUAL_CHECK_REQUIRED" if host == "codex" else "UNVERIFIED"
    return "UNVERIFIED", trust


def configure_global_hook(
    forge_root: Path,
    host: str,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    """Install or repair one host without changing any other host."""
    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported Hook host: {host}")
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        hosts = state["hosts"]
        provider, commands = _current_provider(
            forge_root, host, home=home, codex_home=codex_home
        )
        target_status = provider.detect()
        target_was_configured = target_status.configured
        old_record = hosts.get(host)
        old_provider = None
        rollback = None
        if isinstance(old_record, dict):
            old_provider, _ = _provider_from_record(
                host, old_record, forge_root, home=home, codex_home=codex_home
            )
        same_provider = old_provider is not None and _same_provider(provider, old_provider)
        if old_provider is not None and (
            not same_provider or target_status.state != "CONFIGURED"
        ):
            if provider.config_path == old_provider.config_path:
                if target_status.state == "NOT_CONFIGURED":
                    installed = provider.install()
                    rollback = provider.uninstall
                else:
                    installed = provider.replace_owned(old_provider)
                    rollback = lambda: old_provider.replace_owned(provider)
            else:
                installed = provider.install()
                try:
                    old_provider.uninstall()
                except (OSError, ValueError):
                    if not target_was_configured:
                        provider.uninstall()
                    raise

                def rollback_relocation() -> None:
                    old_provider.install()
                    if not target_was_configured:
                        provider.uninstall()

                rollback = rollback_relocation
        else:
            installed = provider.install()
        previous_record = hosts.get(host)
        preserve_installation = (
            same_provider
            and target_status.state == "CONFIGURED"
            and installed.state == "CONFIGURED"
            and isinstance(previous_record, dict)
            and isinstance(previous_record.get("installedAt"), str)
        )
        hosts[host] = {
            "configPath": str(provider.config_path),
            "commands": commands,
            "events": list(provider.events),
            "installedAt": previous_record.get("installedAt") if preserve_installation else _now(),
        }
        try:
            _save_hook_state(forge_root, state)
        except BaseException:
            if rollback is not None:
                rollback()
            elif not target_was_configured:
                provider.uninstall()
            raise
        return {
            "host": host,
            "configuredHosts": sorted(global_hook_hosts(
                forge_root, home=home, codex_home=codex_home
            )),
            "managedHosts": sorted(hosts),
            "state": installed.state,
            "configPath": str(provider.config_path),
            "events": list(provider.events),
        }


def remove_global_hook(
    forge_root: Path,
    host: str | None = None,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    if host is not None and host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported Hook host: {host}")
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        cleanup: dict[str, str] = {}
        failed = False
        targets = (host,) if host is not None else tuple(SUPPORTED_HOSTS)
        for target in targets:
            record = state["hosts"].get(target)
            recorded_provider = None
            current_provider = None
            outcomes: list[str] = []
            try:
                if isinstance(record, dict):
                    recorded_provider, _ = _provider_from_record(
                        target, record, forge_root,
                        home=home, codex_home=codex_home,
                    )
            except (OSError, ValueError) as error:
                outcomes.append(f"recorded=CLEANUP_FAILED: {error}")
                failed = True
            try:
                current_provider, _ = _current_provider(
                    forge_root, target,
                    home=home, codex_home=codex_home,
                )
            except (OSError, ValueError) as error:
                outcomes.append(f"current=CLEANUP_FAILED: {error}")
                failed = True
            candidates: list[tuple[str, LearningHookProvider, bool]] = []
            if recorded_provider is not None and current_provider is not None:
                if _same_provider(recorded_provider, current_provider):
                    candidates.append(("current", current_provider, True))
                elif recorded_provider.config_path == current_provider.config_path:
                    current_status = current_provider.detect()
                    recorded_status = recorded_provider.detect()
                    provider = (
                        current_provider
                        if current_status.configured or not recorded_status.configured
                        else recorded_provider
                    )
                    candidates.append(("current", provider, True))
                else:
                    candidates.extend((
                        ("recorded", recorded_provider, True),
                        ("current", current_provider, False),
                    ))
            elif recorded_provider is not None:
                candidates.append(("recorded", recorded_provider, True))
            elif current_provider is not None:
                clears_record = (
                    isinstance(record, dict)
                    and record.get("configPath") == str(current_provider.config_path)
                )
                candidates.append(("current", current_provider, clears_record))

            record_cleared = record is None
            for label, provider, clears_record in candidates:
                try:
                    outcome = provider.uninstall().state
                    outcomes.append(f"{label}={outcome}")
                    record_cleared = record_cleared or clears_record
                except (OSError, ValueError) as error:
                    outcomes.append(f"{label}=CLEANUP_FAILED: {error}")
                    failed = True
            if record_cleared:
                state["hosts"].pop(target, None)
            if len(outcomes) == 1 and "=" in outcomes[0]:
                cleanup[target] = outcomes[0].split("=", 1)[1]
            else:
                cleanup[target] = "; ".join(outcomes)
        try:
            _save_hook_state(forge_root, state)
        except OSError as error:
            cleanup["state"] = f"STATE_UPDATE_FAILED: {error}"
            failed = True
        return {
            "host": host,
            "configuredHosts": sorted(global_hook_hosts(
                forge_root, home=home, codex_home=codex_home
            )),
            "managedHosts": sorted(state["hosts"]),
            "state": "PARTIAL" if failed else "NOT_CONFIGURED",
            "cleanup": cleanup,
        }


def global_hook_hosts(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> set[str]:
    """Return every host whose current Forge Hook command is configured."""
    configured = set()
    for host in SUPPORTED_HOSTS:
        try:
            provider, _ = _current_provider(
                forge_root, host, home=home, codex_home=codex_home
            )
            if provider.detect().configured:
                configured.add(host)
        except (OSError, ValueError):
            continue
    return configured


def global_hook_selection(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> str | None:
    """Compatibility view for callers that can represent only one host."""
    configured = global_hook_hosts(
        forge_root, home=home, codex_home=codex_home
    )
    return next(iter(configured)) if len(configured) == 1 else None


def global_hook_status(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        statuses = {}
        for host in SUPPORTED_HOSTS:
            event = _load_last_event(forge_root, host)
            host_record = state.get("hosts", {}).get(host)
            installed_at = (
                host_record.get("installedAt")
                if isinstance(host_record, dict) else None
            )
            try:
                provider, _ = _current_provider(
                    forge_root, host, home=home, codex_home=codex_home
                )
                status = provider.detect()
                config_path = str(status.config_path)
                events = list(status.events)
                detail = status.detail
                config_state = status.state
                configured = status.configured
            except (OSError, ValueError) as error:
                config_path = None
                events = []
                detail = str(error)
                config_state = "REPAIR_REQUIRED"
                configured = False
            event_scope = _event_scope(
                event, configured=configured, installed_at=installed_at
            )
            enabled_status, trust_status = _native_capability_status(host, configured)
            statuses[host] = {
                "state": config_state,
                "configState": config_state,
                "runtimeState": (
                    _runtime_state(event, installed_at)
                    if event_scope == "CURRENT_INSTALLATION"
                    else "NEVER_OBSERVED"
                ),
                "eventScope": event_scope,
                "configured": configured,
                "enabledStatus": enabled_status,
                "trustStatus": trust_status,
                "configPath": config_path,
                "events": events,
                "detail": detail,
                "lastEvent": event,
                "managed": host in state.get("hosts", {}),
            }
        configured_hosts = sorted(
            host for host, status in statuses.items() if status["configured"]
        )
        return {
            "configuredHosts": configured_hosts,
            "configuredReady": bool(configured_hosts),
            "hosts": statuses,
            "lastEvents": {
                host: statuses[host].get("lastEvent") for host in configured_hosts
            },
        }
