# -*- coding: utf-8 -*-
"""Tests for atomic consumption of project-local paused Runtime Envelopes."""

import json
import os
from pathlib import Path

import pytest

from forge_cli.cli import _execute_route
from forge_cli.resolved_context import build_context_from_route
from forge_cli.runtime_composition import initialize_runtime
from forge_cli.runtime_discovery import discover_resumable_runtimes
from forge_cli.runtime_lifecycle import consume_paused_runtime
from forge_cli import runtime_lifecycle


ROOT = Path(__file__).resolve().parents[1]


def _runtime():
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "review spring service"))
    return initialize_runtime(ROOT, manifest, task_statement="resume task")


def test_consume_removes_selected_runtime_from_discovery(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime_path = runtime_directory / "resume.json"
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.chdir(project)

    result = consume_paused_runtime(ROOT, runtime_directory, "resume.json")

    assert result["task_statement"] == "resume task"
    assert not runtime_path.exists()
    assert discover_resumable_runtimes(ROOT, runtime_directory)["candidates"] == []
    assert not list(runtime_directory.glob("*.claim"))


def test_consume_rejects_paths_outside_current_project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    (project / ".forge-runtime").mkdir(parents=True)
    outside.mkdir()
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="current project's"):
        consume_paused_runtime(ROOT, outside, "resume.json")


def test_consume_rejects_path_traversal(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="direct .json filename"):
        consume_paused_runtime(ROOT, runtime_directory, "../resume.json")


def test_consume_restores_runtime_when_claim_cleanup_fails(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime_path = runtime_directory / "resume.json"
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.chdir(project)
    original_unlink = Path.unlink

    def fail_claim_unlink(path, *args, **kwargs):
        if path.suffix == ".claim":
            raise OSError("busy")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_claim_unlink)

    with pytest.raises(RuntimeError, match="original runtime was restored"):
        consume_paused_runtime(ROOT, runtime_directory, "resume.json")

    assert runtime_path.is_file()
    assert not list(runtime_directory.glob("*.claim"))


def test_consume_never_overwrites_runtime_created_while_claim_is_held(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime_path = runtime_directory / "resume.json"
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.chdir(project)
    original_unlink = Path.unlink

    def fail_claim_unlink(path, *args, **kwargs):
        if path.suffix == ".claim":
            raise OSError("busy")
        return original_unlink(path, *args, **kwargs)

    def create_concurrent_runtime_then_fail(source, target, *args, **kwargs):
        Path(target).write_text("concurrent runtime", encoding="utf-8")
        raise FileExistsError(target)

    monkeypatch.setattr(Path, "unlink", fail_claim_unlink)
    monkeypatch.setattr(os, "link", create_concurrent_runtime_then_fail)

    with pytest.raises(RuntimeError, match="new runtime already exists") as captured:
        consume_paused_runtime(ROOT, runtime_directory, "resume.json")

    assert runtime_path.read_text(encoding="utf-8") == "concurrent runtime"
    claim_path = next(runtime_directory.glob("*.claim"))
    assert str(claim_path) in str(captured.value)


def test_consume_reports_duplicate_claim_after_successful_restore(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime_path = runtime_directory / "resume.json"
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.chdir(project)
    original_path_unlink = Path.unlink
    original_os_unlink = os.unlink

    def fail_initial_claim_unlink(path, *args, **kwargs):
        if path.suffix == ".claim":
            raise OSError("busy")
        return original_path_unlink(path, *args, **kwargs)

    def fail_duplicate_claim_unlink(path, *args, **kwargs):
        if str(path).endswith(".claim"):
            raise OSError("still busy")
        return original_os_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_initial_claim_unlink)
    monkeypatch.setattr(os, "unlink", fail_duplicate_claim_unlink)

    with pytest.raises(RuntimeError, match="original runtime was restored") as captured:
        consume_paused_runtime(ROOT, runtime_directory, "resume.json")

    assert runtime_path.is_file()
    claim_path = next(runtime_directory.glob("*.claim"))
    assert "retained duplicate claim" in str(captured.value)
    assert str(claim_path) in str(captured.value)


def test_payload_failure_never_overwrites_concurrent_runtime(tmp_path, monkeypatch):
    project = tmp_path / "project"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime_path = runtime_directory / "resume.json"
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.chdir(project)

    def fail_payload(_document):
        runtime_path.write_text("concurrent runtime", encoding="utf-8")
        raise ValueError("invalid stage")

    monkeypatch.setattr(runtime_lifecycle, "_current_stage", fail_payload)

    with pytest.raises(RuntimeError, match="payload construction failed") as captured:
        consume_paused_runtime(ROOT, runtime_directory, "resume.json")

    assert runtime_path.read_text(encoding="utf-8") == "concurrent runtime"
    claim_path = next(runtime_directory.glob("*.claim"))
    assert str(claim_path) in str(captured.value)
