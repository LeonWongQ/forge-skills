import importlib.util
import os
from pathlib import Path
import sys

import pytest

from forge_cli import codex_skill_sync
from forge_cli.codex_skill_sync import SyncAction, apply_sync, plan_sync, source_snapshot, watch_sync


def _sync_script_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "sync-codex-skills.py"
    spec = importlib.util.spec_from_file_location("sync_codex_skills", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_root(tmp_path: Path) -> Path:
    source = tmp_path / ".claude"
    (source / "forge").mkdir(parents=True)
    (source / "skills" / "alpha").mkdir(parents=True)
    (source / "skills" / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    (source / "skills" / ".system").mkdir()
    return source


def test_plan_creates_forge_and_skill_links_without_system_skill(tmp_path):
    source = _source_root(tmp_path)
    actions = plan_sync(source, tmp_path / ".codex")

    assert [(action.name, action.status) for action in actions] == [("forge", "create"), ("alpha", "create")]


def test_apply_creates_only_missing_links_and_preserves_existing_directory(tmp_path):
    source = _source_root(tmp_path)
    target = tmp_path / ".codex"
    (target / "skills" / "alpha").mkdir(parents=True)
    made = []

    actions = apply_sync(source, target, create_link=lambda path, origin: made.append((path, origin)))

    assert [(action.name, action.status) for action in actions] == [("forge", "create"), ("alpha", "conflict")]
    assert made == [(target / "forge", source / "forge")]


def test_plan_recognizes_existing_links_to_the_same_source(tmp_path, monkeypatch):
    source = _source_root(tmp_path)
    target = tmp_path / ".codex"
    (target / "forge").mkdir(parents=True)
    (target / "skills" / "alpha").mkdir(parents=True)

    def linked_source(path: Path) -> Path:
        return source / "forge" if path.name == "forge" else source / "skills" / path.name

    monkeypatch.setattr(codex_skill_sync, "_link_target", linked_source)

    actions = plan_sync(source, target)

    assert [(action.name, action.status) for action in actions] == [
        ("forge", "unchanged"),
        ("alpha", "unchanged"),
    ]
    assert all(action.detail == "Already linked to project source." for action in actions)


@pytest.mark.skipif(os.name != "nt", reason="Windows extended path syntax")
def test_same_path_accepts_windows_extended_length_prefix(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    extended = Path("\\\\?\\" + str(source))

    assert codex_skill_sync._same_path(extended, source)


def test_source_snapshot_changes_only_for_skill_directories(tmp_path):
    source = _source_root(tmp_path)
    assert source_snapshot(source) == ("alpha",)

    (source / "skills" / "notes").mkdir()
    assert source_snapshot(source) == ("alpha",)


def test_watch_rejects_too_small_interval(tmp_path):
    source = _source_root(tmp_path)
    watcher = watch_sync(source, tmp_path / ".codex", 0.1)

    try:
        next(watcher)
    except ValueError as error:
        assert "at least 0.2" in str(error)
    else:
        raise AssertionError("Expected an invalid watch interval to fail")


def test_watch_default_interval_is_ten_minutes(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync-codex-skills.py"])

    assert _sync_script_module().parse_args().interval == 600.0


def test_watch_cli_rejects_too_small_interval():
    module = _sync_script_module()

    with pytest.raises(SystemExit):
        module.parse_args(["--watch", "--interval", "0"])


def test_render_collapses_healthy_links_by_default(tmp_path, capsys):
    module = _sync_script_module()
    actions = [SyncAction("alpha", tmp_path / "source", tmp_path / "target", "unchanged")]

    module.render(actions, as_json=False)

    output = capsys.readouterr().out
    assert "target" not in output
    assert "Summary: unchanged=1" in output


def test_render_verbose_shows_healthy_links(tmp_path, capsys):
    module = _sync_script_module()
    actions = [SyncAction("alpha", tmp_path / "source", tmp_path / "target", "unchanged")]

    module.render(actions, as_json=False, verbose=True)

    output = capsys.readouterr().out
    assert "[UNCHANGED] alpha" in output
    assert "Summary: unchanged=1" in output
