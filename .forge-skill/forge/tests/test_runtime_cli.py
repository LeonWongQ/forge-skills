# -*- coding: utf-8 -*-
"""CLI tests for Runtime natural-language dispatch."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from forge_cli.cli import _execute_route, _project_runtime_directory, cli
from forge_cli.resolved_context import build_context_from_route
from forge_cli.runtime_composition import initialize_runtime


ROOT = Path(__file__).resolve().parents[1]


def _runtime_for_ask(runtime_id):
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "review spring service"))
    return initialize_runtime(ROOT, manifest, task_statement=f"task {runtime_id}", runtime_id=runtime_id)


def test_ask_short_suspend_command_creates_runtime(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "runtime-suspend --task 简化 return results"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "runtime-suspended"
    assert payload["runtime_path"].startswith(".forge-runtime/")
    assert (project / payload["runtime_path"]).is_file()


def test_runtime_list_rejects_unpartitioned_directory(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    shared = tmp_path / "global-runtime"
    project.mkdir()
    shared.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "runtime-list-paused", "--directory", str(shared)])

    assert result.exit_code != 0
    assert "project's .forge-runtime directory" in result.output


def test_suspend_migrates_legacy_runtime_without_overwriting_new_task(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    legacy = project / ".forge" / "runtime"
    project.mkdir()
    legacy.mkdir(parents=True)
    legacy_file = legacy / "old.json"
    legacy_file.write_text(json.dumps(_runtime_for_ask("legacy")), encoding="utf-8")
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "runtime-suspend", "--task", "new task"])

    assert result.exit_code == 0, result.output
    assert (project / ".forge-runtime" / "old.json").is_file()
    assert not legacy_file.exists()


def test_global_forge_root_keeps_runtime_in_current_project(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    global_root = tmp_path / "home" / ".codex" / "forge"
    project.mkdir()
    global_root.parent.mkdir(parents=True)
    try:
        global_root.symlink_to(ROOT, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(global_root), "--format", "json", "ask", "runtime-suspend --task global runtime"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["runtime_path"] == ".forge-runtime/global-runtime.json"
    assert (project / payload["runtime_path"]).is_file()
    assert _project_runtime_directory(global_root) == project / ".forge-runtime"
    assert not (tmp_path / "home" / ".forge-runtime").exists()


def test_ask_lists_paused_runtime_without_mutating_it(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    runtime = _runtime_for_ask("runtime.list")
    path = runtime_directory / "resume.json"
    path.write_text(json.dumps(runtime), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "runtime-list-paused"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["candidates"][0]["path"] == "resume.json"
    assert path.read_bytes() == original


def test_ask_lists_paused_runtime_with_chinese_query_without_mutating_it(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    path = runtime_directory / "resume.json"
    path.write_text(json.dumps(_runtime_for_ask("runtime.chinese-list")), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "有哪些暂停的 Forge Runtime 任务"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["candidates"][0]["path"] == "resume.json"
    assert path.read_bytes() == original


def test_ask_chinese_suspend_requires_confirmation_before_creating_runtime(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.chdir(project)

    request = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "暂停 Forge Runtime 任务“整理接口文档”"])

    assert request.exit_code == 0, request.output
    payload = json.loads(request.output)
    assert payload == {
        "mode": "runtime-suspend-confirmation-required",
        "task_statement": "整理接口文档",
        "mutated": False,
        "persistence_question": "是否需要将 Forge Runtime 任务“整理接口文档”持久化保存到当前项目？",
        "confirmation": "确认挂起 Forge Runtime 任务“整理接口文档”",
    }
    assert not (project / ".forge-runtime").exists()

    confirmed = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", payload["confirmation"]])

    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["mode"] == "runtime-suspended"
    assert len(list((project / ".forge-runtime").glob("*.json"))) == 1


def test_ask_unqualified_suspend_does_not_create_runtime(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "暂停这个任务"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] != "runtime-suspended"
    assert not (project / ".forge-runtime").exists()


def test_ask_persistent_suspend_request_requires_confirmation(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "将这个记录点任务持久化挂起"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "runtime-suspend-confirmation-required"
    assert payload["task_statement"] == "这个记录点任务"
    assert payload["mutated"] is False
    assert not (project / ".forge-runtime").exists()


def test_ask_continue_without_filename_only_lists_candidates(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    path = runtime_directory / "resume.json"
    path.write_text(json.dumps(_runtime_for_ask("runtime.pending")), encoding="utf-8")
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "继续 Forge Runtime 任务"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["candidates"][0]["path"] == "resume.json"
    assert path.exists()


def test_ask_continue_named_runtime_consumes_only_that_runtime(tmp_path, monkeypatch):
    runner = CliRunner()
    project = tmp_path / "consumer"
    runtime_directory = project / ".forge-runtime"
    runtime_directory.mkdir(parents=True)
    selected = runtime_directory / "resume.json"
    retained = runtime_directory / "retain.json"
    selected.write_text(json.dumps(_runtime_for_ask("runtime.selected")), encoding="utf-8")
    retained.write_text(json.dumps(_runtime_for_ask("runtime.retained")), encoding="utf-8")
    monkeypatch.chdir(project)

    result = runner.invoke(cli, ["--root", str(ROOT), "--format", "json", "ask", "继续 resume.json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["runtime_id"] == "runtime.selected"
    assert not selected.exists()
    assert retained.exists()
