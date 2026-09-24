"""Global learning Hook registration and single-host ownership."""

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


STATE_VERSION = "2.0"
LEGACY_STATE_VERSION = "1.0"
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
        return {"schemaVersion": STATE_VERSION, "selectedHost": None, "hosts": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read learning Hook state: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid learning Hook state: {path}")
    hosts = value.get("hosts")
    if not isinstance(hosts, dict):
        raise ValueError(f"invalid learning Hook state: {path}")
    if value.get("schemaVersion") == LEGACY_STATE_VERSION:
        projects = value.get("projects")
        if not isinstance(projects, dict):
            raise ValueError(f"invalid legacy learning Hook state: {path}")
        selected = {
            item.get("host") for item in projects.values()
            if isinstance(item, dict) and item.get("host") in SUPPORTED_HOSTS
        }
        return {
            "schemaVersion": STATE_VERSION,
            "selectedHost": next(iter(selected)) if len(selected) == 1 else None,
            "hosts": hosts,
        }
    if value.get("schemaVersion") != STATE_VERSION:
        raise ValueError(f"unsupported learning Hook state: {path}")
    selected = value.get("selectedHost")
    if selected is not None and selected not in SUPPORTED_HOSTS:
        raise ValueError(f"invalid selected Hook host: {path}")
    return value


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
    """Select exactly one user-global host and remove other Forge Hooks."""
    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported Hook host: {host}")
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        hosts = state["hosts"]
        previous = state.get("selectedHost")
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
        state["selectedHost"] = host
        try:
            # Persist a valid selected target before removing another host. If
            # cleanup later fails, the old entry remains recorded and can be
            # reconciled safely on the next request.
            _save_hook_state(forge_root, state)
        except BaseException:
            if rollback is not None:
                rollback()
            elif previous != host and not target_was_configured:
                provider.uninstall()
            raise
        cleanup: dict[str, str] = {}
        for other in SUPPORTED_HOSTS:
            if other == host or other not in hosts:
                continue
            other_provider, _ = _provider_from_record(
                other, hosts.get(other), forge_root, home=home, codex_home=codex_home
            )
            try:
                cleanup[other] = other_provider.uninstall().state
                hosts.pop(other, None)
            except (OSError, ValueError) as error:
                cleanup[other] = f"CLEANUP_FAILED: {error}"
        if cleanup:
            try:
                _save_hook_state(forge_root, state)
            except OSError as error:
                cleanup["state"] = f"STATE_UPDATE_FAILED: {error}"
        partial = any(value.startswith(("CLEANUP_FAILED", "STATE_UPDATE_FAILED")) for value in cleanup.values())
        return {
            "selectedHost": host,
            "state": "PARTIAL" if partial else installed.state,
            "configPath": str(provider.config_path),
            "events": list(provider.events),
            "previousHost": previous,
            "cleanup": cleanup,
        }


def remove_global_hook(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        previous = state.get("selectedHost")
        cleanup: dict[str, str] = {}
        failed = False
        for host in tuple(state["hosts"]):
            provider, _ = _provider_from_record(
                host, state["hosts"].get(host), forge_root,
                home=home, codex_home=codex_home,
            )
            try:
                cleanup[host] = provider.uninstall().state
                state["hosts"].pop(host, None)
            except (OSError, ValueError) as error:
                cleanup[host] = f"CLEANUP_FAILED: {error}"
                failed = True
        if previous not in state["hosts"]:
            state["selectedHost"] = None
        try:
            _save_hook_state(forge_root, state)
        except OSError as error:
            cleanup["state"] = f"STATE_UPDATE_FAILED: {error}"
            failed = True
        return {
            "selectedHost": state.get("selectedHost"),
            "state": "PARTIAL" if failed else "NOT_CONFIGURED",
            "previousHost": previous,
            "cleanup": cleanup,
        }


def global_hook_selection(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> str | None:
    selected = load_hook_state(forge_root).get("selectedHost")
    if selected not in SUPPORTED_HOSTS:
        return None
    try:
        provider, _ = _current_provider(
            forge_root, selected, home=home, codex_home=codex_home
        )
        return selected if provider.detect().configured else None
    except (OSError, ValueError):
        return None


def global_hook_status(
    forge_root: Path,
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    state_path = hook_state_path(forge_root)
    with _REGISTRY_LOCK, _registry_file_lock(state_path):
        state = load_hook_state(forge_root)
        selected = state.get("selectedHost")
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
                "selected": selected == host,
            }
        return {
            "selectedHost": selected,
            "selectedReady": bool(
                selected in statuses and statuses[selected]["configured"]
            ),
            "hosts": statuses,
            "lastEvent": statuses.get(selected, {}).get("lastEvent"),
        }
