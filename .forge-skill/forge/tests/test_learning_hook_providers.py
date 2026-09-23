"""Tests for user-scoped learning Hook configuration adapters."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

import pytest

from forge_cli.learning_hook_providers import (
    HOOK_MARKER,
    LearningHookProvider,
    build_hook_commands,
    provider_for,
)


def commands(host: str) -> dict[str, str]:
    events = ("after-agent-response", "stop") if host == "cursor" else ("stop",)
    return {
        event: f'python hook.py --host {host} --event {event} --forge-hook-marker {HOOK_MARKER}'
        for event in events
    }


@pytest.mark.parametrize(
    ("host", "relative"),
    [
        ("claude-code", Path(".claude/settings.json")),
        ("cursor", Path(".cursor/hooks.json")),
        ("codex", Path(".codex/hooks.json")),
    ],
)
def test_provider_uses_user_global_configuration(host, relative, tmp_path):
    provider = provider_for(host, commands(host), home=tmp_path)

    assert provider.config_path == tmp_path / relative
    assert provider.detect().state == "NOT_CONFIGURED"


@pytest.mark.parametrize("host", ("claude-code", "codex", "cursor"))
def test_install_is_idempotent_and_uninstall_preserves_user_hooks(host, tmp_path):
    provider = provider_for(host, commands(host), home=tmp_path)
    provider.config_path.parent.mkdir(parents=True)
    if host == "cursor":
        original = {"version": 1, "hooks": {"beforeShellExecution": [{"command": "user-hook"}]}}
    else:
        original = {
            "model": "user-choice",
            "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "user-hook"}]}]},
        }
    provider.config_path.write_text(json.dumps(original), encoding="utf-8")

    assert provider.install().state == "CONFIGURED"
    first = provider.config_path.read_bytes()
    assert provider.install().state == "CONFIGURED"
    assert provider.config_path.read_bytes() == first
    assert provider.uninstall().state == "NOT_CONFIGURED"

    restored = json.loads(provider.config_path.read_text(encoding="utf-8"))
    for key, value in original.items():
        assert restored[key] == value


def test_cursor_installs_response_buffer_and_stop_finalizer(tmp_path):
    provider = provider_for("cursor", commands("cursor"), home=tmp_path)

    provider.install()

    config = json.loads(provider.config_path.read_text(encoding="utf-8"))
    assert config["version"] == 1
    assert len(config["hooks"]["afterAgentResponse"]) == 1
    assert len(config["hooks"]["stop"]) == 1
    assert HOOK_MARKER in config["hooks"]["afterAgentResponse"][0]["command"]


@pytest.mark.parametrize("host", ("claude-code", "codex"))
def test_stop_hosts_install_matcher_free_command_group(host, tmp_path):
    provider = provider_for(host, commands(host), home=tmp_path)

    provider.install()

    config = json.loads(provider.config_path.read_text(encoding="utf-8"))
    event_name = "Stop"
    group = config["hooks"][event_name][0]
    assert "matcher" not in group
    assert group["hooks"][0]["type"] == "command"
    if host == "codex":
        assert group["hooks"][0]["async"] is False
        assert group["hooks"][0]["timeoutSec"] == 5
    else:
        assert group["hooks"][0]["timeout"] == 5


def test_replace_owned_accepts_the_same_forge_command_with_legacy_timeout(tmp_path):
    old_commands = commands("codex")
    old_provider = provider_for("codex", old_commands, home=tmp_path)
    old_provider.install()
    config = json.loads(old_provider.config_path.read_text(encoding="utf-8"))
    config["hooks"]["Stop"][0]["hooks"][0]["timeoutSec"] = 2
    old_provider.config_path.write_text(json.dumps(config), encoding="utf-8")
    replacement_python = tmp_path / "replacement-python.exe"
    replacement_python.write_bytes(b"")
    hook_script = tmp_path / "new-hook.py"
    hook_script.write_text("# replacement", encoding="utf-8")
    hook_script.with_suffix(".ps1").write_text("# launcher", encoding="utf-8")
    replacement_commands = build_hook_commands(
        replacement_python, hook_script, "codex", forge_root=tmp_path / "forge"
    )
    replacement = provider_for("codex", replacement_commands, home=tmp_path)

    status = replacement.replace_owned(old_provider)

    assert status.state == "CONFIGURED"
    updated = json.loads(replacement.config_path.read_text(encoding="utf-8"))
    hook = updated["hooks"]["Stop"][0]["hooks"][0]
    assert hook["timeoutSec"] == 5
    if os.name == "nt":
        assert base64.b64encode(str(replacement_python).encode("utf-8")).decode("ascii") in hook["command"]
    else:
        assert str(replacement_python) in hook["command"]


@pytest.mark.skipif(os.name != "nt", reason="Codex Windows launcher")
@pytest.mark.parametrize("shell", ("powershell", "cmd"))
def test_codex_command_starts_a_python_path_with_spaces(tmp_path, shell):
    python = Path(__import__("sys").executable)
    script = tmp_path / "host_capture_hook.py"
    script.write_text("import sys; print('args=' + ','.join(sys.argv[1:]))", encoding="utf-8")
    launcher = script.with_suffix(".ps1")
    launcher.write_bytes(
        (Path(__file__).parents[2] / "skills" / "learning-collector" / "scripts"
         / "host_capture_hook.ps1").read_bytes()
    )
    command = build_hook_commands(python, script, "codex", forge_root=tmp_path)["stop"]

    prefix = (
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
        if shell == "powershell" else ["cmd.exe", "/d", "/s", "/c"]
    )
    result = subprocess.run(prefix + [command], capture_output=True, text=True, timeout=10, check=False)

    assert result.returncode == 0, result.stderr
    assert "args=--host,codex,--event,stop,--forge-hook-marker,forge-learning-capture-v1" in result.stdout


def test_codex_migrates_legacy_lowercase_config_key(tmp_path):
    provider = provider_for("codex", commands("codex"), home=tmp_path)
    provider.config_path.parent.mkdir(parents=True)
    config = {"hooks": {"stop": [provider._entry("stop")]}}
    provider.config_path.write_text(json.dumps(config), encoding="utf-8")

    assert provider.detect().state == "CONFIG_DRIFTED"
    replacement = provider.replace_owned(provider)

    assert replacement.state == "CONFIGURED"
    migrated = json.loads(provider.config_path.read_text(encoding="utf-8"))
    assert "stop" not in migrated["hooks"]
    assert "Stop" in migrated["hooks"]


def test_modified_owned_hook_is_reported_and_never_overwritten_or_removed(tmp_path):
    provider = provider_for("claude-code", commands("claude-code"), home=tmp_path)
    provider.install()
    config = json.loads(provider.config_path.read_text(encoding="utf-8"))
    config["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 99
    provider.config_path.write_text(json.dumps(config), encoding="utf-8")
    before = provider.config_path.read_bytes()

    assert provider.detect().state == "CONFIG_DRIFTED"
    with pytest.raises(ValueError, match="incomplete, duplicated, or modified"):
        provider.install()
    replacement = provider_for(
        "claude-code",
        {"stop": commands("claude-code")["stop"] + " --replacement"},
        home=tmp_path,
    )
    with pytest.raises(ValueError, match="incomplete or duplicated"):
        replacement.replace_owned(provider)
    with pytest.raises(ValueError, match="refusing to remove"):
        provider.uninstall()
    assert provider.config_path.read_bytes() == before


def test_invalid_user_configuration_is_not_overwritten(tmp_path):
    provider = provider_for("cursor", commands("cursor"), home=tmp_path)
    provider.config_path.parent.mkdir(parents=True)
    provider.config_path.write_text('{"version":2,"hooks":{}}', encoding="utf-8")

    assert provider.detect().state == "INVALID_CONFIG"
    with pytest.raises(ValueError, match="unsupported Cursor Hook version"):
        provider.install()


def test_build_commands_requires_existing_runtime_and_script(tmp_path):
    python = tmp_path / "python.exe"
    script = tmp_path / "host_capture_hook.py"
    python.write_bytes(b"")
    script.write_text("# hook", encoding="utf-8")

    built = build_hook_commands(python, script, "cursor")

    assert set(built) == {"after-agent-response", "stop"}
    assert all(HOOK_MARKER in command for command in built.values())
    assert all(str(python) in command and str(script) in command for command in built.values())


def test_provider_rejects_commands_without_ownership_marker(tmp_path):
    with pytest.raises(ValueError, match="ownership marker"):
        LearningHookProvider("codex", tmp_path / "hooks.json", {"stop": "python hook.py"})
