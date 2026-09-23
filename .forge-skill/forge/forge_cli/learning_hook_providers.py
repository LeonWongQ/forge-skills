"""User-scoped native Hook configuration for Forge learning capture."""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .personal_hook_state import _atomic_write, _json_bytes, _load_json


HOOK_MARKER = "forge-learning-capture-v1"
HOOK_TIMEOUT_SECONDS = 5
SUPPORTED_HOSTS = ("codex", "claude-code", "cursor")


@dataclass(frozen=True)
class HookStatus:
    host: str
    state: str
    config_path: Path
    events: tuple[str, ...]
    detail: str | None = None

    @property
    def configured(self) -> bool:
        return self.state == "CONFIGURED"


def _command(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def build_hook_commands(
    python_executable: Path,
    hook_script: Path,
    host: str,
    *,
    forge_root: Path | None = None,
) -> dict[str, str]:
    """Build commands with an inspectable ownership marker."""
    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported Hook host: {host}")
    if not python_executable.is_file():
        raise ValueError(f"Python executable does not exist: {python_executable}")
    if not hook_script.is_file():
        raise ValueError(f"Hook script does not exist: {hook_script}")
    launcher = hook_script.with_suffix(".ps1") if os.name == "nt" and host == "codex" else None
    if launcher is not None and not launcher.is_file():
        raise ValueError(f"Codex Hook launcher does not exist: {launcher}")
    events = ("after-agent-response", "stop") if host == "cursor" else ("stop",)
    commands = {}
    for event in events:
        parts = [
            str(python_executable.absolute()),
            str(hook_script.absolute()),
            "--host", host,
            "--event", event,
            "--forge-hook-marker", HOOK_MARKER,
        ]
        if forge_root is not None:
            parts.extend(("--forge-root", str(forge_root.absolute())))
        if launcher is not None:
            python_path = base64.b64encode(str(python_executable.absolute()).encode("utf-8")).decode("ascii")
            script_path = base64.b64encode(str(hook_script.absolute()).encode("utf-8")).decode("ascii")
            parts = [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(launcher.absolute()),
                python_path, script_path, *parts[2:],
            ]
        commands[event] = _command(parts)
    return commands


class LearningHookProvider:
    """Safely manage one host's Forge-owned global Hook entries."""

    def __init__(self, host: str, config_path: Path, commands: Mapping[str, str]):
        if host not in SUPPORTED_HOSTS:
            raise ValueError(f"unsupported Hook host: {host}")
        self.host = host
        self.config_path = config_path
        self.commands = dict(commands)
        expected = {"after-agent-response", "stop"} if host == "cursor" else {"stop"}
        if set(self.commands) != expected:
            raise ValueError(f"{host} requires Hook commands for: {', '.join(sorted(expected))}")
        if any(HOOK_MARKER not in command for command in self.commands.values()):
            raise ValueError("every Forge Hook command must contain the ownership marker")

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self._event_name(event) for event in self.commands)

    def _event_name(self, event: str) -> str:
        if self.host == "cursor":
            return "afterAgentResponse" if event == "after-agent-response" else "stop"
        if self.host == "codex":
            # Codex's hooks.json uses the legacy-compatible config key `Stop`.
            # The command payload still receives the runtime event `stop`.
            return "Stop"
        return "Stop"

    def _event_names(self, event: str) -> tuple[str, ...]:
        """Return current and known legacy names for safe migration."""
        current = self._event_name(event)
        if self.host == "codex" and current == "Stop":
            # `stop` was written by an earlier Forge release. Treat it as a
            # legacy location so configure/replace can migrate it safely.
            return (current, "stop")
        return (current,)

    def _entry(self, event: str) -> dict[str, Any]:
        command = self.commands[event]
        if self.host == "cursor":
            return {"command": command, "timeout": HOOK_TIMEOUT_SECONDS}
        if self.host == "codex":
            # Codex uses its native configured-hook schema. `timeout` is the
            # Claude-style field; Codex requires `async` and uses `timeoutSec`.
            return {
                "hooks": [{
                    "type": "command",
                    "command": command,
                    "async": False,
                    "timeoutSec": HOOK_TIMEOUT_SECONDS,
                }]
            }
        return {
            "hooks": [{
                "type": "command",
                "command": command,
                "timeout": HOOK_TIMEOUT_SECONDS,
            }]
        }

    def _same_owned_command(self, event: str, entry: Any) -> bool:
        """Recognize an older Forge entry when only its timeout changed."""
        command = self.commands[event]
        if self.host == "cursor":
            return (
                isinstance(entry, dict)
                and set(entry).issubset({"command", "timeout"})
                and entry.get("command") == command
                and entry.get("timeout") == 2
            )
        if not isinstance(entry, dict) or set(entry) != {"hooks"}:
            return False
        hooks = entry.get("hooks")
        if not isinstance(hooks, list) or len(hooks) != 1:
            return False
        hook = hooks[0]
        if self.host == "codex":
            if not isinstance(hook, dict) or hook.get("type") != "command" or hook.get("command") != command:
                return False
            return (
                set(hook) == {"type", "command", "timeout"}
                and hook.get("timeout") in (2, HOOK_TIMEOUT_SECONDS)
            ) or (
                set(hook) == {"type", "command", "async", "timeoutSec"}
                and hook.get("async") is False
                and hook.get("timeoutSec") == 2
            )
        return (
            isinstance(hook, dict)
            and set(hook) == {"type", "command", "timeout"}
            and hook.get("type") == "command"
            and hook.get("command") == command
            and hook.get("timeout") == 2
        )

    @staticmethod
    def _hooks(config: dict[str, Any], *, create: bool) -> dict[str, Any]:
        hooks = config.get("hooks")
        if hooks is None and create:
            hooks = {}
            config["hooks"] = hooks
        if hooks is None:
            return {}
        if not isinstance(hooks, dict):
            raise ValueError("Hook configuration field 'hooks' must be an object")
        return hooks

    @staticmethod
    def _entries(hooks: dict[str, Any], event: str, *, create: bool) -> list[Any]:
        entries = hooks.get(event)
        if entries is None and create:
            entries = []
            hooks[event] = entries
        if entries is None:
            return []
        if not isinstance(entries, list):
            raise ValueError(f"Hook event '{event}' must be an array")
        return entries

    def _inspect(self, config: dict[str, Any]) -> HookStatus:
        if self.host == "cursor":
            version = config.get("version")
            if version not in (None, 1):
                return HookStatus(
                    self.host, "INVALID_CONFIG", self.config_path, self.events,
                    f"unsupported Cursor Hook version: {version}",
                )
        try:
            hooks = self._hooks(config, create=False)
            exact = 0
            marked = 0
            expected_count = len(self.commands)
            for event in self.commands:
                expected = self._entry(event)
                for event_name in self._event_names(event):
                    for entry in self._entries(hooks, event_name, create=False):
                        if HOOK_MARKER in json.dumps(entry, ensure_ascii=False):
                            marked += 1
                            if event_name == self._event_name(event) and entry == expected:
                                exact += 1
        except ValueError as error:
            return HookStatus(
                self.host, "INVALID_CONFIG", self.config_path, self.events, str(error)
            )
        if marked == 0:
            return HookStatus(self.host, "NOT_CONFIGURED", self.config_path, self.events)
        if marked == exact == expected_count:
            return HookStatus(self.host, "CONFIGURED", self.config_path, self.events)
        return HookStatus(
            self.host, "CONFIG_DRIFTED", self.config_path, self.events,
            "Forge-owned Hook entries are incomplete, duplicated, or modified",
        )

    def detect(self) -> HookStatus:
        try:
            config, _ = _load_json(self.config_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            return HookStatus(
                self.host, "INVALID_CONFIG", self.config_path, self.events, str(error)
            )
        return self._inspect(config)

    def install(self) -> HookStatus:
        config, before = _load_json(self.config_path)
        status = self._inspect(config)
        if status.state == "CONFIGURED":
            return status
        if status.state != "NOT_CONFIGURED":
            raise ValueError(status.detail or f"cannot install {self.host} Hook")
        if self.host == "cursor":
            config.setdefault("version", 1)
        hooks = self._hooks(config, create=True)
        for event in self.commands:
            self._entries(hooks, self._event_name(event), create=True).append(self._entry(event))
        self._write_if_unchanged(before, config)
        installed = self.detect()
        if not installed.configured:
            raise OSError(f"{self.host} Hook verification failed: {installed.state}")
        return installed

    def replace_owned(self, previous: "LearningHookProvider") -> HookStatus:
        """Atomically replace one exact Forge-owned entry in the same config file."""
        if self.host != previous.host or self.config_path != previous.config_path:
            raise ValueError("Hook replacement requires the same host and configuration path")
        config, before = _load_json(self.config_path)
        hooks = self._hooks(config, create=True)
        for event in previous.commands:
            old_entry = previous._entry(event)
            matches = []
            for event_name in previous._event_names(event):
                entries = self._entries(hooks, event_name, create=False)
                matches.extend(
                    (event_name, index)
                    for index, entry in enumerate(entries)
                    if entry == old_entry or previous._same_owned_command(event, entry)
                )
            if len(matches) != 1:
                raise ValueError("previous Forge-owned Hook is incomplete or duplicated")
            event_name, index = matches[0]
            entries = self._entries(hooks, event_name, create=False)
            entries.pop(index)
            if not entries:
                hooks.pop(event_name, None)
        if self.host == "cursor":
            config.setdefault("version", 1)
        hooks = self._hooks(config, create=True)
        for event in self.commands:
            self._entries(hooks, self._event_name(event), create=True).append(self._entry(event))
        self._write_if_unchanged(before, config)
        installed = self.detect()
        if not installed.configured:
            raise OSError(f"{self.host} Hook replacement verification failed: {installed.state}")
        return installed

    def uninstall(self) -> HookStatus:
        config, before = _load_json(self.config_path)
        current = self._inspect(config)
        if current.state == "NOT_CONFIGURED":
            return current
        if current.state == "INVALID_CONFIG":
            raise ValueError(current.detail or f"invalid {self.host} Hook configuration")
        hooks = self._hooks(config, create=False)
        drifted = False
        for event in self.commands:
            expected = self._entry(event)
            for event_name in self._event_names(event):
                entries = self._entries(hooks, event_name, create=False)
                marked = [
                    entry for entry in entries
                    if HOOK_MARKER in json.dumps(entry, ensure_ascii=False)
                ]
                if any(
                    entry != expected and not self._same_owned_command(event, entry)
                    for entry in marked
                ):
                    drifted = True
                    break
            if drifted:
                break
        if drifted:
            raise ValueError("Forge-owned Hook was modified; refusing to remove unknown content")
        for event in self.commands:
            expected = self._entry(event)
            for event_name in self._event_names(event):
                entries = self._entries(hooks, event_name, create=False)
                hooks[event_name] = [
                    entry for entry in entries
                    if entry != expected and not self._same_owned_command(event, entry)
                ]
                if not hooks[event_name]:
                    hooks.pop(event_name)
        if not hooks:
            config.pop("hooks", None)
        self._write_if_unchanged(before, config)
        return self.detect()

    def _write_if_unchanged(self, before: bytes | None, config: dict[str, Any]) -> None:
        try:
            current = self.config_path.read_bytes()
        except FileNotFoundError:
            current = None
        if current != before:
            raise OSError(f"Hook configuration changed concurrently: {self.config_path}")
        _atomic_write(self.config_path, _json_bytes(config))


def provider_for(
    host: str,
    commands: Mapping[str, str],
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> LearningHookProvider:
    """Create a provider for the current user's global host configuration."""
    user_home = home or Path.home()
    if host == "claude-code":
        path = user_home / ".claude" / "settings.json"
    elif host == "cursor":
        path = user_home / ".cursor" / "hooks.json"
    elif host == "codex":
        configured = os.getenv("CODEX_HOME") if home is None and codex_home is None else None
        root = codex_home or (Path(configured).expanduser() if configured else user_home / ".codex")
        path = root / "hooks.json"
    else:
        raise ValueError(f"unsupported Hook host: {host}")
    return LearningHookProvider(host, path, commands)
