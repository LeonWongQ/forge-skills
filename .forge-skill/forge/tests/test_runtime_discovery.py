# -*- coding: utf-8 -*-
"""Tests for read-only paused Runtime Envelope discovery."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from forge_cli.cli import _execute_route, cli
from forge_cli.runtime_composition import initialize_runtime
from forge_cli.runtime_discovery import discover_resumable_runtimes
from forge_cli.resolved_context import build_context_from_route


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_forge_data(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))


def _runtime(runtime_id, status="ready"):
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "review spring service"))
    envelope = initialize_runtime(ROOT, manifest, task_statement=f"task {runtime_id}", runtime_id=runtime_id)
    envelope["status"] = status
    return envelope


def test_discovery_lists_valid_nonterminal_envelopes_only(tmp_path):
    (tmp_path / "ready.json").write_text(json.dumps(_runtime("runtime.ready")), encoding="utf-8")
    (tmp_path / "completed.json").write_text(json.dumps(_runtime("runtime.completed", "completed")), encoding="utf-8")
    (tmp_path / "invalid.json").write_text("not json", encoding="utf-8")

    result = discover_resumable_runtimes(ROOT, tmp_path)

    assert [candidate["runtime_id"] for candidate in result["candidates"]] == ["runtime.ready"]
    assert result["summary"] == {"scanned": 3, "resumable": 1, "terminal": 1, "invalid": 1}
    candidate = result["candidates"][0]
    assert candidate["current_stage_id"] == "engine.discover"
    assert candidate["attempt"] == 0
    assert any(item["path"] == "invalid.json" for item in result["diagnostics"])


def test_discovery_does_not_mutate_runtime_files(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(_runtime("runtime.read-only"), ensure_ascii=False), encoding="utf-8")
    original = path.read_bytes()

    discover_resumable_runtimes(ROOT, tmp_path)

    assert path.read_bytes() == original


def test_runtime_list_paused_cli_reports_explicit_directory(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    (runtime_directory / "runtime.json").write_text(json.dumps(_runtime("runtime.cli")), encoding="utf-8")
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli, ["--root", str(ROOT), "--format", "json", "runtime-list-paused", "--directory", str(runtime_directory)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "runtime-list-paused"
    assert payload["candidates"][0]["path"] == "runtime.json"
