# -*- coding: utf-8 -*-
"""Tests for the read-only personal SessionStart advisory."""

import io
import json
from pathlib import Path

from forge_cli.personal_session_start_hook import ADVISORY, _forge_root, main


def _event(project: Path) -> io.StringIO:
    return io.StringIO(json.dumps({"cwd": str(project)}))


def test_no_runtime_directory_emits_nothing(tmp_path):
    output = io.StringIO()

    assert main(_event(tmp_path), output) == 0
    assert output.getvalue() == ""


def test_candidate_emits_only_constant_advisory(tmp_path, monkeypatch):
    forge = tmp_path / ".claude" / "forge"
    (forge / "forge_cli").mkdir(parents=True)
    (forge / "registry").mkdir()
    (forge / "registry" / "modules.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".forge-runtime").mkdir(parents=True)
    monkeypatch.setattr("forge_cli.personal_session_start_hook._discover", lambda *_: True)
    output = io.StringIO()

    assert main(_event(tmp_path), output) == 0
    payload = json.loads(output.getvalue())
    assert payload["hookSpecificOutput"]["additionalContext"] == ADVISORY
    assert "runtime_id" not in output.getvalue()


def test_codex_deployment_is_discovered_from_its_config_directory(tmp_path, monkeypatch):
    forge = tmp_path / ".codex" / "forge"
    (forge / "forge_cli").mkdir(parents=True)
    (forge / "registry").mkdir()
    (forge / "registry" / "modules.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".forge-runtime").mkdir(parents=True)
    monkeypatch.setattr("forge_cli.personal_session_start_hook._configured_tool", lambda _: "codex")
    monkeypatch.setattr("forge_cli.personal_session_start_hook._discover", lambda *_: True)
    output = io.StringIO()

    assert _forge_root(tmp_path, "codex") == forge.resolve()
    assert main(_event(tmp_path), output) == 0
    assert json.loads(output.getvalue())["hookSpecificOutput"]["additionalContext"] == ADVISORY


def test_central_runtime_is_discovered_when_project_facade_is_missing(tmp_path, monkeypatch):
    project = tmp_path / "project"
    forge = project / ".claude" / "forge"
    (forge / "forge_cli").mkdir(parents=True)
    (forge / "registry").mkdir()
    (forge / "registry" / "modules.json").write_text("{}", encoding="utf-8")
    identity = project / ".forge-skill" / "learning" / "project.json"
    identity.parent.mkdir(parents=True)
    identity.write_text(
        json.dumps({"schemaVersion": "1.0", "projectId": "project-central"}),
        encoding="utf-8",
    )
    data_root = tmp_path / "forge-data"
    paused = data_root / "projects" / "project-central" / "runtime" / "paused"
    paused.mkdir(parents=True)
    (paused / "resume.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data_root))
    discovered = []
    monkeypatch.setattr(
        "forge_cli.personal_session_start_hook._discover",
        lambda _forge, directory: discovered.append(directory) or True,
    )
    output = io.StringIO()

    assert main(_event(project), output) == 0

    facade = project / ".forge-runtime"
    assert discovered == [facade]
    assert facade.resolve() == paused.resolve()
    assert json.loads(output.getvalue())["hookSpecificOutput"]["additionalContext"] == ADVISORY


def test_invalid_event_never_blocks_startup():
    output = io.StringIO()

    assert main(io.StringIO("not-json"), output) == 0
    assert output.getvalue() == ""
