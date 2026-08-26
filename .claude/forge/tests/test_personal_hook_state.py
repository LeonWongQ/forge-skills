# -*- coding: utf-8 -*-
"""Tests for personal Forge hook ownership management."""

import json
from pathlib import Path

import pytest

import forge_cli.personal_hook_state as hook_state

from forge_cli.personal_hook_state import (
    HOOK_MARKER,
    create_manifest,
    install_hook,
    list_manifests,
    load_manifest,
    uninstall_hook,
)


def _hook_script(tmp_path: Path) -> Path:
    script = tmp_path / "project" / ".claude" / "forge" / "forge_cli" / "personal_session_start_hook.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('hook')\n", encoding="utf-8")
    return script


def test_hook_install_preserves_project_settings_and_is_idempotent(tmp_path):
    home = tmp_path / "home"
    settings_path = tmp_path / "project" / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"env": {"A": "B"}, "hooks": {"PreToolUse": [{"x": 1}]}}, ensure_ascii=False), encoding="utf-8")
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)
    first = json.loads(settings_path.read_text(encoding="utf-8"))
    install_hook(load_manifest(manifest["install_id"], home), settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)
    second = json.loads(settings_path.read_text(encoding="utf-8"))

    assert first["env"] == {"A": "B"}
    assert first["hooks"]["PreToolUse"] == [{"x": 1}]
    assert len(second["hooks"]["SessionStart"]) == 1
    assert HOOK_MARKER in json.dumps(second, ensure_ascii=False)
    assert Path(load_manifest(manifest["install_id"], home)["hook"]["script_path"]) == _hook_script(tmp_path).absolute()
    assert not (home / ".claude" / "hooks" / "forge-sessionstart-advisory.py").exists()


def test_hook_uninstall_preserves_later_user_settings_changes(tmp_path):
    home = tmp_path / "home"
    settings_path = home / ".claude" / "settings.json"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["model"] = "user-change"
    settings["hooks"]["SessionStart"].append({"hooks": [{"type": "command", "command": "other"}]})
    settings_path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")

    assert uninstall_hook(load_manifest(manifest["install_id"], home), home=home) == "removed"
    updated = json.loads(settings_path.read_text(encoding="utf-8"))
    assert updated["model"] == "user-change"
    assert updated["hooks"]["SessionStart"] == [{"hooks": [{"type": "command", "command": "other"}]}]


def test_invalid_settings_are_not_overwritten(tmp_path):
    home = tmp_path / "home"
    settings_path = home / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("not-json", encoding="utf-8")
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    with pytest.raises(json.JSONDecodeError):
        install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)

    assert settings_path.read_text(encoding="utf-8") == "not-json"


def test_hook_uninstall_accepts_empty_project_settings_after_manual_hook_removal(tmp_path):
    home = tmp_path / "home"
    settings_path = tmp_path / "project" / ".claude" / "settings.local.json"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)
    settings_path.write_text("{}", encoding="utf-8")

    assert uninstall_hook(load_manifest(manifest["install_id"], home), home=home) == "already-absent"
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {}


def test_hook_uninstall_keeps_shared_hook_for_another_installation(tmp_path):
    home = tmp_path / "home"
    settings_path = home / ".claude" / "settings.json"
    source = _hook_script(tmp_path)
    first = create_manifest(project=tmp_path / "first", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    second = create_manifest(project=tmp_path / "second", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    install_hook(first, settings_path=settings_path, hook_script=source, home=home)
    install_hook(second, settings_path=settings_path, hook_script=source, home=home)

    assert uninstall_hook(load_manifest(first["install_id"], home), home=home) == "retained-for-other-installations"
    assert HOOK_MARKER in settings_path.read_text(encoding="utf-8")
    assert uninstall_hook(load_manifest(second["install_id"], home), home=home) == "removed"
    assert HOOK_MARKER not in settings_path.read_text(encoding="utf-8")


def test_hook_uninstall_does_not_share_ownership_across_settings_files(tmp_path):
    home = tmp_path / "home"
    source = _hook_script(tmp_path)
    first_settings = tmp_path / "first" / ".claude" / "settings.local.json"
    second_settings = tmp_path / "second" / ".claude" / "settings.local.json"
    first = create_manifest(project=tmp_path / "first", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    second = create_manifest(project=tmp_path / "second", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    install_hook(first, settings_path=first_settings, hook_script=source, home=home)
    install_hook(second, settings_path=second_settings, hook_script=source, home=home)

    assert uninstall_hook(load_manifest(first["install_id"], home), home=home) == "removed"
    assert HOOK_MARKER not in first_settings.read_text(encoding="utf-8")
    assert HOOK_MARKER in second_settings.read_text(encoding="utf-8")
    assert load_manifest(first["install_id"], home)["hook"] is None
    assert isinstance(load_manifest(second["install_id"], home)["hook"], dict)


@pytest.mark.parametrize("settings_exists", [False, True])
def test_hook_install_rolls_back_settings_when_manifest_save_fails(tmp_path, monkeypatch, settings_exists):
    home = tmp_path / "home"
    settings_path = tmp_path / "project" / ".claude" / "settings.local.json"
    before = b'{"model":"original"}\n'
    if settings_exists:
        settings_path.parent.mkdir(parents=True)
        settings_path.write_bytes(before)
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    def fail_save(*_args, **_kwargs):
        raise OSError("manifest unavailable")

    monkeypatch.setattr(hook_state, "save_manifest", fail_save)

    with pytest.raises(OSError, match="manifest unavailable"):
        install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)

    assert manifest["hook"] is None
    if settings_exists:
        assert settings_path.read_bytes() == before
    else:
        assert not settings_path.exists()


def test_hook_uninstall_rolls_back_settings_when_manifest_save_fails(tmp_path, monkeypatch):
    home = tmp_path / "home"
    settings_path = tmp_path / "project" / ".claude" / "settings.local.json"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)
    before = settings_path.read_bytes()
    installed_hook = manifest["hook"]

    def fail_save(*_args, **_kwargs):
        raise OSError("manifest unavailable")

    monkeypatch.setattr(hook_state, "save_manifest", fail_save)

    with pytest.raises(OSError, match="manifest unavailable"):
        uninstall_hook(manifest, home=home)

    assert settings_path.read_bytes() == before
    assert manifest["hook"] == installed_hook


def test_hook_install_does_not_overwrite_concurrent_change_during_rollback(tmp_path, monkeypatch):
    home = tmp_path / "home"
    settings_path = tmp_path / "project" / ".claude" / "settings.local.json"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    def fail_after_external_change(*_args, **_kwargs):
        settings_path.write_text('{"model":"external-change"}\n', encoding="utf-8")
        raise OSError("manifest unavailable")

    monkeypatch.setattr(hook_state, "save_manifest", fail_after_external_change)

    with pytest.raises(OSError, match="inspect residual settings"):
        install_hook(manifest, settings_path=settings_path, hook_script=_hook_script(tmp_path), home=home)

    assert json.loads(settings_path.read_text(encoding="utf-8")) == {"model": "external-change"}
    assert manifest["hook"] is None


def test_manifest_is_user_scoped_and_durable(tmp_path):
    home = tmp_path / "home"
    manifest = create_manifest(
        project=tmp_path / "project",
        source_root=tmp_path / "source",
        tool="claude",
        created_links=[{"name": "forge", "path": "x", "source": "y"}],
        home=home,
    )

    loaded = load_manifest(manifest["install_id"], home)
    assert loaded["created_links"][0]["name"] == "forge"
    assert [item["install_id"] for item in list_manifests(home)] == [manifest["install_id"]]


def test_create_manifest_rejects_duplicate_install_id_without_overwriting(tmp_path):
    home = tmp_path / "home"
    original = create_manifest(
        project=tmp_path / "first",
        source_root=tmp_path / "source",
        tool="claude",
        created_links=[{"name": "forge", "path": "x", "source": "y"}],
        install_id="fixed-id",
        home=home,
    )

    with pytest.raises(ValueError, match="already exists"):
        create_manifest(
            project=tmp_path / "second",
            source_root=tmp_path / "other-source",
            tool="cursor",
            created_links=[],
            install_id="fixed-id",
            home=home,
        )

    assert load_manifest("fixed-id", home) == original
