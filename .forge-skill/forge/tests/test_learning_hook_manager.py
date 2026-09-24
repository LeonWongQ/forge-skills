"""Integration tests for global Hook ownership and invocation correlation."""

from __future__ import annotations

from contextlib import closing, contextmanager
import base64
import importlib.util
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import forge_cli.learning_hook_manager as hook_manager
import forge_cli.learning_invocations as learning_invocations
from forge_cli.learning_collector import _registry_file_lock, collect_imported_result
from forge_cli.learning_hook_manager import (
    configure_global_hook,
    global_hook_status,
    hook_event_status_path,
    hook_state_path,
    load_hook_state,
    remove_global_hook,
)
from forge_cli.learning_invocations import (
    begin_invocation as _begin_invocation,
    current_host_from_environment,
    handle_host_event,
)
from forge_cli.runtime_paths import _project_id


def begin_invocation(forge_root, project_root, skill, **kwargs):
    configured_hosts = load_hook_state(forge_root).get("hosts", {})
    current_host = kwargs.pop(
        "current_host", next(iter(configured_hosts), "unknown")
    )
    return _begin_invocation(
        forge_root, project_root, skill, current_host=current_host, **kwargs
    )


def bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle" / "forge"
    data = root.parent / "forge-data"
    scripts = root.parent / "skills" / "learning-collector" / "scripts"
    data.mkdir(parents=True)
    scripts.mkdir(parents=True)
    (data / "runtime.json").write_text(
        json.dumps({
            "schemaVersion": "1.0",
            "pythonExecutable": sys.executable,
            "directCollectionTimeoutSeconds": 2,
        }),
        encoding="utf-8",
    )
    (scripts / "host_capture_hook.py").write_text("# test hook", encoding="utf-8")
    (scripts / "host_capture_hook.ps1").write_text("# test launcher", encoding="utf-8")
    return root


def project(tmp_path: Path, name: str = "project") -> Path:
    root = tmp_path / name
    learning = root / ".forge-skill" / "learning"
    learning.mkdir(parents=True)
    (learning / "config.json").write_text(
        json.dumps({"schemaVersion": "1.0", "enabledSkills": ["code-review"]}),
        encoding="utf-8",
    )
    return root


def fallback(
    forge_root: Path,
    project_root: Path,
    invocation: dict,
    content: str,
    *,
    skill: str = "code-review",
) -> Path:
    envelope = {
        "runtime_id": f"direct.{invocation['invocationId']}",
        "resolved_context": {
            "selection": {"skill": f"skill.{skill.replace('-', '_')}"}
        },
        "stage_progress": {"active_request": {"stage_id": "direct.delivery"}},
    }
    result = {
        "status": "succeeded",
        "output": {"conclusion": content},
        "metadata": {"source": "direct_host_skill"},
        "collection": {
            "invocationId": invocation["invocationId"],
            "source": "SKILL_CONTRACT",
            "hookHost": invocation.get("hookHost"),
            "hookStatus": "PENDING" if invocation.get("hookHost") else "NOT_CONFIGURED",
        },
    }
    database = collect_imported_result(forge_root, envelope, result, project=project_root)
    assert database is not None
    return database


def test_configuring_all_hosts_preserves_every_owned_hook(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"

    codex = configure_global_hook(forge_root, "codex", home=home)
    claude = configure_global_hook(forge_root, "claude-code", home=home)
    cursor_result = configure_global_hook(forge_root, "cursor", home=home)

    assert codex["configuredHosts"] == ["codex"]
    assert claude["configuredHosts"] == ["claude-code", "codex"]
    assert cursor_result["configuredHosts"] == ["claude-code", "codex", "cursor"]
    assert cursor_result["managedHosts"] == ["claude-code", "codex", "cursor"]
    codex_config = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    claude_config = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cursor = json.loads((home / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert "Stop" in codex_config["hooks"]
    assert "Stop" in claude_config["hooks"]
    assert set(cursor["hooks"]) == {"afterAgentResponse", "stop"}
    state = json.loads(hook_state_path(forge_root).read_text(encoding="utf-8"))
    assert state["schemaVersion"] == "3.0"
    assert set(state["hosts"]) == {"codex", "claude-code", "cursor"}
    assert "selectedHost" not in state


def test_removing_one_global_hook_preserves_other_hosts(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    configure_global_hook(forge_root, "cursor", home=home)
    removed = remove_global_hook(forge_root, "claude-code", home=home)

    assert removed["configuredHosts"] == ["cursor"]
    assert removed["cleanup"] == {"claude-code": "NOT_CONFIGURED"}
    claude = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "hooks" not in claude
    cursor = json.loads((home / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert set(cursor["hooks"]) == {"afterAgentResponse", "stop"}


def test_configure_response_distinguishes_configured_and_managed_hosts(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    claude_path = home / ".claude" / "settings.json"
    claude = json.loads(claude_path.read_text(encoding="utf-8"))
    claude.pop("hooks")
    claude_path.write_text(json.dumps(claude), encoding="utf-8")

    configured = configure_global_hook(forge_root, "cursor", home=home)

    assert configured["configuredHosts"] == ["cursor"]
    assert configured["managedHosts"] == ["claude-code", "cursor"]


def test_remove_response_distinguishes_configured_and_managed_hosts(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    configure_global_hook(forge_root, "cursor", home=home)
    claude_path = home / ".claude" / "settings.json"
    claude = json.loads(claude_path.read_text(encoding="utf-8"))
    claude.pop("hooks")
    claude_path.write_text(json.dumps(claude), encoding="utf-8")

    removed = remove_global_hook(forge_root, "cursor", home=home)

    assert removed["configuredHosts"] == []
    assert removed["managedHosts"] == ["claude-code"]


def test_remove_cleans_recorded_and_current_codex_homes(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    recorded_home = tmp_path / "codex-recorded"
    current_home = tmp_path / "codex-current"
    configure_global_hook(
        forge_root, "codex", home=home, codex_home=recorded_home
    )
    current_home.mkdir(parents=True)
    current_config = current_home / "hooks.json"
    current_config.write_bytes((recorded_home / "hooks.json").read_bytes())

    removed = remove_global_hook(
        forge_root, "codex", home=home, codex_home=current_home
    )

    assert removed["state"] == "NOT_CONFIGURED"
    assert removed["configuredHosts"] == []
    assert removed["managedHosts"] == []
    assert removed["cleanup"]["codex"] == (
        "recorded=NOT_CONFIGURED; current=NOT_CONFIGURED"
    )
    recorded = json.loads(
        (recorded_home / "hooks.json").read_text(encoding="utf-8")
    )
    current = json.loads(current_config.read_text(encoding="utf-8"))
    assert "hooks" not in recorded
    assert "hooks" not in current


def test_removing_without_host_explicitly_removes_all_hooks(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    configure_global_hook(forge_root, "cursor", home=home)

    removed = remove_global_hook(forge_root, home=home)

    assert removed["configuredHosts"] == []
    assert set(removed["cleanup"]) == {"codex", "claude-code", "cursor"}
    assert load_hook_state(forge_root)["hosts"] == {}


def test_remove_all_persists_successful_removals_when_other_providers_fail(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["directCollectionTimeoutSeconds"] = 0
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    removed = remove_global_hook(forge_root, home=home)

    assert removed["state"] == "PARTIAL"
    assert "recorded=NOT_CONFIGURED" in removed["cleanup"]["codex"]
    assert "current=CLEANUP_FAILED" in removed["cleanup"]["codex"]
    assert removed["cleanup"]["claude-code"].startswith("CLEANUP_FAILED")
    assert removed["cleanup"]["cursor"].startswith("CLEANUP_FAILED")
    assert load_hook_state(forge_root)["hosts"] == {}
    codex = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert "hooks" not in codex


def test_legacy_v1_state_migrates_to_independent_host_semantics(tmp_path):
    forge_root = bundle(tmp_path)
    path = hook_state_path(forge_root)
    path.write_text(json.dumps({
        "schemaVersion": "1.0",
        "projects": {
            "project-a": {"host": "claude-code"},
            "project-b": {"host": "claude-code"},
        },
        "hosts": {"claude-code": {"configPath": "legacy"}},
    }), encoding="utf-8")

    state = load_hook_state(forge_root)

    assert state == {
        "schemaVersion": "3.0",
        "hosts": {"claude-code": {"configPath": "legacy"}},
    }


def test_legacy_v2_state_preserves_all_hosts_and_discards_selection(tmp_path):
    forge_root = bundle(tmp_path)
    path = hook_state_path(forge_root)
    path.write_text(json.dumps({
        "schemaVersion": "2.0",
        "selectedHost": "codex",
        "hosts": {
            "codex": {"configPath": "codex"},
            "cursor": {"configPath": "cursor"},
        },
    }), encoding="utf-8")

    state = load_hook_state(forge_root)

    assert state["schemaVersion"] == "3.0"
    assert set(state["hosts"]) == {"codex", "cursor"}
    assert "selectedHost" not in state


@pytest.mark.parametrize(
    ("variable", "host"),
    [
        ("CODEX_SESSION_ID", "codex"),
        ("CLAUDE_CODE_SESSION_ID", "claude-code"),
        ("CURSOR_CONVERSATION_ID", "cursor"),
    ],
)
def test_current_host_detection_uses_unambiguous_native_environment(
    monkeypatch, variable, host,
):
    for name in (
        "CODEX_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID",
        "CLAUDECODE", "CURSOR_CONVERSATION_ID", "CURSOR_GENERATION_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, "native-session")

    assert current_host_from_environment() == host


def test_current_host_detection_rejects_conflicting_host_environments(monkeypatch):
    monkeypatch.setenv("CODEX_SESSION_ID", "codex-session")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "claude-session")

    assert current_host_from_environment() is None


def test_unconfigured_current_host_does_not_create_pending_marker(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)

    invocation = _begin_invocation(
        forge_root, project_root, "code-review", current_host="codex", hook_home=home
    )

    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / invocation["projectId"]
        / "learning" / "invocations"
    )
    assert invocation["hookHost"] is None
    assert invocation["hookExpected"] is False
    assert invocation["reason"] == "HOOK_NOT_CONFIGURED_FOR_HOST"
    assert not invocation_dir.exists()


@pytest.mark.parametrize("host", ["codex", "claude-code", "cursor"])
def test_each_configured_current_host_creates_its_own_pending_marker(tmp_path, host):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    for configured_host in ("codex", "claude-code", "cursor"):
        configure_global_hook(forge_root, configured_host, home=home)

    invocation = _begin_invocation(
        forge_root, project_root, "code-review", current_host=host, hook_home=home
    )

    assert invocation["hookExpected"] is True
    assert invocation["hookHost"] == host
    marker = (
        forge_root.parent / "forge-data" / "projects" / invocation["projectId"]
        / "learning" / "invocations" / f"{invocation['invocationId']}.json"
    )
    assert json.loads(marker.read_text(encoding="utf-8"))["host"] == host


def test_begin_rejects_unknown_current_host_name(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)

    with pytest.raises(ValueError, match="unsupported current host"):
        _begin_invocation(
            forge_root, project_root, "code-review", current_host="typo-host"
        )


def test_one_global_host_applies_to_enabled_skills_in_multiple_projects(tmp_path):
    forge_root = bundle(tmp_path)
    first = project(tmp_path, "first")
    second = project(tmp_path, "second")
    configure_global_hook(forge_root, "codex", home=tmp_path / "home")

    first_invocation = begin_invocation(forge_root, first, "code-review", hook_home=tmp_path / "home")
    second_invocation = begin_invocation(forge_root, second, "code-review", hook_home=tmp_path / "home")

    assert first_invocation["hookHost"] == "codex"
    assert second_invocation["hookHost"] == "codex"
    assert first_invocation["projectId"] != second_invocation["projectId"]


def test_hook_capture_profiles_any_enabled_skill_and_survives_fallback(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["report"],
    }), encoding="utf-8")
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    monkeypatch.setenv("CODEX_SESSION_ID", "session-report")
    invocation = begin_invocation(forge_root, project_root, "report", hook_home=home)

    handled = handle_host_event(
        forge_root, "codex", "stop", {
            "cwd": str(project_root),
            "session_id": "session-report",
            "turn_id": "turn-report",
            "last_assistant_message": "  # Report\r\n\r\nResult  ",
        }, hook_home=home,
    )

    assert handled.get("action") == "CAPTURED", handled
    database = (
        forge_root.parent / "forge-data" / "projects" / invocation["projectId"]
        / "learning" / "report" / "learning.sqlite"
    )
    fallback(forge_root, project_root, invocation, "structured report", skill="report")
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT output_json, host_output_json, metadata_json, capture_source "
            "FROM learning_records"
        ).fetchone()
    assert json.loads(row[0]) == {"conclusion": "structured report"}
    assert json.loads(row[1]) == {"finalResponse": "  # Report\n\nResult  "}
    metadata = json.loads(row[2])
    assert metadata["source"] == "direct_host_skill"
    assert metadata["hookCapture"] == {
        "schemaVersion": "1.0",
        "skill": "report",
        "host": "codex",
        "event": "stop",
        "responseSource": "stop-payload",
        "attribution": "TURN_UNIQUE",
        "matchedInvocationCount": 1,
        "matchedSkills": ["report"],
        "response": {
            "format": "MARKDOWN",
            "characters": 20,
            "nonWhitespaceCharacters": 13,
            "lines": 3,
            "startsWithHeading": True,
            "codeFenceCount": 0,
        },
    }
    assert row[3] == "SKILL_CONTRACT"


def test_claude_stop_upgrades_one_fallback_record(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "claude-code", home=tmp_path / "home")
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    database = fallback(forge_root, project_root, invocation, "structured fallback")
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE learning_records SET run_status = ?, diagnostics_json = ?",
            ("failed", json.dumps({"error": "skill failure"})),
        )

    handled = handle_host_event(
        forge_root,
        "claude-code",
        "stop",
        {"cwd": str(project_root), "session_id": "session-1", "last_assistant_message": "final response"},
        hook_home=tmp_path / "home",
    )

    assert handled["action"] == "CAPTURED"
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM learning_records").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0]["output_json"]) == {"conclusion": "structured fallback"}
    assert json.loads(rows[0]["host_output_json"]) == {"finalResponse": "final response"}
    assert rows[0]["capture_source"] == "SKILL_CONTRACT"
    assert rows[0]["fallback_captured"] == 1
    assert rows[0]["run_status"] == "failed"
    assert json.loads(rows[0]["diagnostics_json"]) == {"error": "skill failure"}
    hook_capture = json.loads(rows[0]["metadata_json"])["hookCapture"]
    assert hook_capture["skill"] == "code-review"
    assert hook_capture["attribution"] == "SESSION_SCOPED"
    assert hook_capture["response"]["format"] == "TEXT"


def test_host_trace_records_matching_and_collection_without_response_content(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    monkeypatch.setenv("CODEX_SESSION_ID", "private-session")
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    fallback(forge_root, project_root, invocation, "structured fallback")
    steps = []

    result = handle_host_event(
        forge_root, "codex", "stop",
        {"cwd": str(project_root), "session_id": "private-session",
         "last_assistant_message": "private final response"},
        hook_home=home,
        trace=lambda step, **fields: steps.append({"step": step, **fields}),
    )

    assert result.get("action") == "CAPTURED", (result, steps)
    assert [entry["step"] for entry in steps] == [
        "handler_entered", "project_resolution", "host_configuration", "pending_lookup",
        "identity_check", "invocation_match", "response_check", "collection_started",
        "collection_finished",
    ]
    assert steps[5]["invocationIds"] == [invocation["invocationId"]]
    assert steps[-1]["stored"] is True
    trace_text = json.dumps(steps)
    assert "private-session" not in trace_text
    assert "private final response" not in trace_text
    assert str(project_root) not in trace_text


def test_late_hook_after_review_is_not_reported_as_captured(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    monkeypatch.setenv("CODEX_SESSION_ID", "session-late")
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    database = fallback(forge_root, project_root, invocation, "reviewed fallback")
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("UPDATE learning_records SET reviewed = 1")
    steps = []

    result = handle_host_event(
        forge_root, "codex", "stop", {
            "cwd": str(project_root), "session_id": "session-late",
            "last_assistant_message": "late response",
        }, hook_home=home,
        trace=lambda step, **fields: steps.append({"step": step, **fields}),
    )

    assert result == {
        "handled": False,
        "reason": "COLLECTION_SKIPPED",
        "invocationIds": [invocation["invocationId"]],
    }
    assert steps[-1]["step"] == "collection_finished"
    assert steps[-1]["stored"] is False
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT hook_status, hook_captured_at, host_output_json FROM learning_records"
        ).fetchone()
    assert row == ("PENDING", None, None)


def test_claude_begin_uses_native_session_identity(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "claude-session")

    invocation = begin_invocation(
        forge_root, project_root, "code-review", hook_home=home
    )

    marker_path = (
        forge_root.parent / "forge-data" / "projects" / invocation["projectId"]
        / "learning" / "invocations" / f'{invocation["invocationId"]}.json'
    )
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker["hostIdentity"] == {"sessionId": "claude-session"}


def test_host_trace_explains_missing_pending_invocation(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "codex", home=tmp_path / "home")
    _project_id(forge_root, project_root)
    steps = []

    result = handle_host_event(
        forge_root, "codex", "stop", {"cwd": str(project_root)},
        hook_home=tmp_path / "home",
        trace=lambda step, **fields: steps.append({"step": step, **fields}),
    )

    assert result == {"handled": False, "reason": "NO_PENDING_INVOCATION"}
    assert steps[-1] == {
        "step": "pending_lookup", "count": 0, "reason": "NO_PENDING_INVOCATION",
    }


def test_cursor_buffers_response_then_finalizes_on_stop(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    database = fallback(forge_root, project_root, invocation, "fallback")
    common = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-1",
        "generation_id": "generation-1",
    }

    buffered = handle_host_event(
        forge_root, "cursor", "after-agent-response", {**common, "text": "cursor final response"},
        hook_home=tmp_path / "home",
    )
    captured = handle_host_event(
        forge_root, "cursor", "stop", {**common, "status": "completed"},
        hook_home=tmp_path / "home",
    )

    assert buffered["action"] == "BUFFERED"
    assert captured["action"] == "CAPTURED"
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT output_json, host_output_json, capture_source, hook_status FROM learning_records"
        ).fetchone()
    assert json.loads(row[0]) == {"conclusion": "fallback"}
    assert json.loads(row[1]) == {"finalResponse": "cursor final response"}
    assert row[2:] == ("SKILL_CONTRACT", "CAPTURED")


@pytest.mark.skipif(sys.platform != "win32", reason="Cursor drive-root form is Windows-only")
def test_cursor_resolves_slash_prefixed_windows_workspace_root(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    fallback(forge_root, project_root, invocation, "fallback")
    workspace_root = f"/{project_root.as_posix()}"
    common = {
        "workspace_roots": [workspace_root],
        "conversation_id": "conversation-1",
        "generation_id": "generation-1",
    }

    buffered = handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**common, "text": "cursor final response"}, hook_home=home,
    )
    captured = handle_host_event(
        forge_root, "cursor", "stop", common, hook_home=home,
    )

    assert buffered["invocationId"] == invocation["invocationId"]
    assert captured["invocationId"] == invocation["invocationId"]


def test_cursor_stop_recovers_response_from_local_transcript(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    database = fallback(forge_root, project_root, invocation, "fallback")
    transcript_root = home / ".cursor" / "projects"
    transcript_root.mkdir(parents=True)
    transcript = transcript_root / "session.jsonl"
    transcript.write_text("\n".join([
        json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "review"}]}}),
        json.dumps({"role": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read"},
            {"type": "text", "text": "recovered final response"},
        ]}}),
        json.dumps({"type": "turn_ended", "status": "success"}),
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        learning_invocations, "_cursor_projects_root",
        lambda: transcript_root.resolve(),
    )

    captured = handle_host_event(
        forge_root, "cursor", "stop", {
            "workspace_roots": [str(project_root)],
            "conversation_id": "conversation-1",
            "generation_id": "generation-1",
            "transcript_path": str(transcript),
        }, hook_home=home,
    )

    assert captured["invocationId"] == invocation["invocationId"]
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT host_output_json, hook_status FROM learning_records"
        ).fetchone()
    assert json.loads(row[0]) == {"finalResponse": "recovered final response"}
    assert row[1] == "CAPTURED"


def test_cursor_transcript_recovery_does_not_reuse_a_previous_turn(tmp_path, monkeypatch):
    transcript_root = tmp_path / ".cursor" / "projects"
    transcript_root.mkdir(parents=True)
    transcript = transcript_root / "session.jsonl"
    transcript.write_text("\n".join([
        json.dumps({"role": "user", "message": {"content": "first"}}),
        json.dumps({"role": "assistant", "message": {"content": [
            {"type": "text", "text": "previous response"},
        ]}}),
        json.dumps({"type": "turn_ended", "status": "success"}),
        json.dumps({"role": "user", "message": {"content": "second"}}),
        json.dumps({"type": "turn_ended", "status": "success"}),
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        learning_invocations, "_cursor_projects_root",
        lambda: transcript_root.resolve(),
    )

    result = learning_invocations._cursor_transcript_response({
        "transcript_path": str(transcript),
    })

    assert result is None


@pytest.mark.parametrize(
    "current_turn",
    [
        [
            {"role": "user", "message": {"content": "failed turn"}},
            {"role": "assistant", "message": {"content": "partial response"}},
            {"type": "turn_ended", "status": "failed"},
        ],
        [
            {"role": "user", "message": {"content": "unfinished turn"}},
            {"role": "assistant", "message": {"content": "partial response"}},
        ],
    ],
    ids=("failed-latest-turn", "unterminated-latest-turn"),
)
def test_cursor_transcript_recovery_never_crosses_an_unsuccessful_latest_turn(
    tmp_path, monkeypatch, current_turn,
):
    transcript_root = tmp_path / ".cursor" / "projects"
    transcript_root.mkdir(parents=True)
    transcript = transcript_root / "session.jsonl"
    entries = [
        {"role": "user", "message": {"content": "previous turn"}},
        {"role": "assistant", "message": {"content": "previous response"}},
        {"type": "turn_ended", "status": "success"},
        *current_turn,
    ]
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        learning_invocations, "_cursor_projects_root",
        lambda: transcript_root.resolve(),
    )

    result = learning_invocations._cursor_transcript_response({
        "transcript_path": str(transcript),
    })

    assert result is None


def test_cursor_events_require_conversation_and_generation_identity(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")

    result = handle_host_event(
        forge_root,
        "cursor",
        "after-agent-response",
        {
            "workspace_roots": [str(project_root)],
            "conversation_id": "conversation-only",
            "text": "must not bind",
        },
        hook_home=tmp_path / "home",
    )

    assert result == {"handled": False, "reason": "HOST_IDENTITY_MISSING"}
    marker = next((
        forge_root.parent / "forge-data" / "projects" / invocation["projectId"]
        / "learning" / "invocations"
    ).glob("inv-*.json"))
    assert "hostIdentity" not in json.loads(marker.read_text(encoding="utf-8"))


def test_multiple_skills_bound_to_same_host_turn_are_all_finalized(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-1")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-1")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    second = begin_invocation(forge_root, project_root, "plan", hook_home=tmp_path / "home")
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-1",
        "generation_id": "generation-1",
    }

    buffered = handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "shared host response"}, hook_home=tmp_path / "home",
    )
    captured = handle_host_event(
        forge_root, "cursor", "stop", payload, hook_home=tmp_path / "home",
    )

    assert set(buffered["invocationIds"]) == {first["invocationId"], second["invocationId"]}
    assert set(captured["invocationIds"]) == {first["invocationId"], second["invocationId"]}
    shared_capture_ids = set()
    for skill in ("code-review", "plan"):
        database = (
            forge_root.parent / "forge-data" / "projects" / first["projectId"]
            / "learning" / skill / "learning.sqlite"
        )
        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                "SELECT host_output_json, hook_status, metadata_json, shared_capture_id, "
                "shared_capture_complete "
                "FROM learning_records"
            ).fetchone()
        assert json.loads(row[0]) == {"finalResponse": "shared host response"}
        assert row[1] == "CAPTURED"
        hook_capture = json.loads(row[2])["hookCapture"]
        assert hook_capture["attribution"] == "SHARED_HOST_TURN"
        assert hook_capture["matchedInvocationCount"] == 2
        assert hook_capture["matchedSkills"] == ["code-review", "plan"]
        shared_capture_ids.add(hook_capture["sharedCaptureId"])
        assert row[3] == hook_capture["sharedCaptureId"]
        assert row[4] == 1
    assert len(shared_capture_ids) == 1
    assert next(iter(shared_capture_ids)).startswith("shared-")


def test_shared_capture_completion_failure_cleans_group_and_markers(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-rollback")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-rollback")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    second = begin_invocation(forge_root, project_root, "plan", hook_home=tmp_path / "home")
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-rollback",
        "generation_id": "generation-rollback",
    }
    handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "shared response"}, hook_home=tmp_path / "home",
    )
    original_persisted = learning_invocations._hook_capture_persisted
    persisted_calls = 0

    def install_failure_after_collection(database, invocation_id, host):
        nonlocal persisted_calls
        stored = original_persisted(database, invocation_id, host)
        persisted_calls += 1
        if persisted_calls == 2:
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute(
                    """CREATE TRIGGER reject_shared_completion
                       BEFORE UPDATE OF shared_capture_complete ON learning_records
                       WHEN NEW.shared_capture_complete = 1
                       BEGIN SELECT RAISE(ABORT, 'forced shared completion failure'); END"""
                )
        return stored

    monkeypatch.setattr(
        learning_invocations, "_hook_capture_persisted", install_failure_after_collection,
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced shared completion failure"):
        handle_host_event(
            forge_root, "cursor", "stop", payload, hook_home=tmp_path / "home",
        )

    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert list(invocation_dir.glob("inv-*.json")) == []
    for skill in ("code-review", "plan"):
        database = (
            forge_root.parent / "forge-data" / "projects" / first["projectId"]
            / "learning" / skill / "learning.sqlite"
        )
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 0


def test_shared_capture_persistence_failure_cleans_group_and_markers(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-incomplete")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-incomplete")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    second = begin_invocation(forge_root, project_root, "plan", hook_home=tmp_path / "home")
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-incomplete",
        "generation_id": "generation-incomplete",
    }
    handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "shared response"}, hook_home=tmp_path / "home",
    )
    original_persisted = learning_invocations._hook_capture_persisted
    persisted_calls = 0

    def skip_second_member(database, invocation_id, host):
        nonlocal persisted_calls
        persisted_calls += 1
        return persisted_calls == 1 and original_persisted(database, invocation_id, host)

    monkeypatch.setattr(
        learning_invocations, "_hook_capture_persisted", skip_second_member,
    )

    result = handle_host_event(
        forge_root, "cursor", "stop", payload, hook_home=tmp_path / "home",
    )

    assert result["handled"] is False
    assert result["reason"] == "SHARED_CAPTURE_INCOMPLETE"
    assert set(result["invocationIds"]) == {
        first["invocationId"], second["invocationId"],
    }
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert list(invocation_dir.glob("inv-*.json")) == []
    for skill in ("code-review", "plan"):
        database = (
            forge_root.parent / "forge-data" / "projects" / first["projectId"]
            / "learning" / skill / "learning.sqlite"
        )
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 0


def test_failed_shared_capture_cleanup_rolls_back_and_keeps_markers(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-cleanup-rollback")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-cleanup-rollback")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    second = begin_invocation(forge_root, project_root, "plan", hook_home=home)
    databases = {
        first["invocationId"]: fallback(forge_root, project_root, first, "first fallback"),
        second["invocationId"]: fallback(
            forge_root, project_root, second, "second fallback", skill="plan",
        ),
    }
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    ordered_ids = sorted((first["invocationId"], second["invocationId"]))
    with closing(sqlite3.connect(databases[ordered_ids[1]])) as connection, connection:
        connection.execute(
            """CREATE TRIGGER reject_failed_group_cleanup
               BEFORE UPDATE OF hook_status ON learning_records
               WHEN NEW.hook_status = 'MISSED'
               BEGIN SELECT RAISE(ABORT, 'forced cleanup failure'); END"""
        )
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-cleanup-rollback",
        "generation_id": "generation-cleanup-rollback",
    }
    handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "shared response"}, hook_home=home,
    )
    persisted_calls = 0
    original_persisted = learning_invocations._hook_capture_persisted

    def fail_second_persistence_check(database, invocation_id, host):
        nonlocal persisted_calls
        persisted_calls += 1
        return persisted_calls == 1 and original_persisted(database, invocation_id, host)

    monkeypatch.setattr(
        learning_invocations, "_hook_capture_persisted", fail_second_persistence_check,
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced cleanup failure"):
        handle_host_event(
            forge_root, "cursor", "stop", payload, hook_home=home,
        )

    assert {path.stem for path in invocation_dir.glob("inv-*.json")} == set(ordered_ids)
    for database in databases.values():
        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                "SELECT hook_status, host_output_json FROM learning_records"
            ).fetchone()
        assert row[0] == "CAPTURED"
        assert json.loads(row[1]) == {"finalResponse": "shared response"}


def test_shared_capture_empty_member_marks_all_fallbacks_missed_and_cleans_hook_data(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-empty-member")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-empty-member")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    first_database = fallback(forge_root, project_root, first, "first fallback")
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-empty-member",
        "generation_id": "generation-empty-member",
    }
    handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "buffered first response"}, hook_home=home,
    )
    second = begin_invocation(forge_root, project_root, "plan", hook_home=home)
    second_database = fallback(
        forge_root, project_root, second, "second fallback", skill="plan",
    )

    result = handle_host_event(
        forge_root, "cursor", "stop", payload, hook_home=home,
    )

    assert result["handled"] is False
    assert result["reason"] == "SHARED_CAPTURE_INCOMPLETE"
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert list(invocation_dir.glob("inv-*.json")) == []
    for database, expected in (
        (first_database, "first fallback"),
        (second_database, "second fallback"),
    ):
        with closing(sqlite3.connect(database)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM learning_records").fetchone()
        assert json.loads(row["output_json"])["conclusion"] == expected
        assert row["capture_source"] == "SKILL_CONTRACT"
        assert row["hook_status"] == "MISSED"
        assert row["shared_capture_id"] is None
        assert row["shared_capture_complete"] == 0
        assert row["host_output_json"] is None
        assert row["hook_captured_at"] is None
        assert "hookCapture" not in json.loads(row["metadata_json"])


@pytest.mark.parametrize("with_fallback", [False, True], ids=("hook-only", "skill-fallback"))
def test_expired_shared_markers_clean_records_left_by_an_interrupted_hook(
    tmp_path, monkeypatch, with_fallback,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-interrupted")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-interrupted")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    second = begin_invocation(forge_root, project_root, "plan", hook_home=home)
    databases = {}
    if with_fallback:
        databases["code-review"] = fallback(
            forge_root, project_root, first, "first fallback",
        )
        databases["plan"] = fallback(
            forge_root, project_root, second, "second fallback", skill="plan",
        )
    payload = {
        "workspace_roots": [str(project_root)],
        "conversation_id": "conversation-interrupted",
        "generation_id": "generation-interrupted",
    }
    handle_host_event(
        forge_root, "cursor", "after-agent-response",
        {**payload, "text": "shared response"}, hook_home=home,
    )
    original_collect = learning_invocations.collect_imported_result
    collected = 0

    def interrupt_after_first_commit(*args, **kwargs):
        nonlocal collected
        database = original_collect(*args, **kwargs)
        collected += 1
        if collected == 1:
            raise KeyboardInterrupt("simulated host termination")
        return database

    monkeypatch.setattr(
        learning_invocations, "collect_imported_result", interrupt_after_first_commit,
    )

    with pytest.raises(KeyboardInterrupt, match="simulated host termination"):
        handle_host_event(
            forge_root, "cursor", "stop", payload, hook_home=home,
        )

    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    for path in invocation_dir.glob("inv-*.json"):
        marker = json.loads(path.read_text(encoding="utf-8"))
        marker["expiresAt"] = "2000-01-01T00:00:00Z"
        path.write_text(json.dumps(marker), encoding="utf-8")

    learning_invocations._purge_expired_markers(forge_root, invocation_dir)

    assert list(invocation_dir.glob("inv-*.json")) == []
    learning_root = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"] / "learning"
    )
    if with_fallback:
        for database in databases.values():
            with closing(sqlite3.connect(database)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute("SELECT * FROM learning_records").fetchone()
            assert row["capture_source"] == "SKILL_CONTRACT"
            assert row["hook_status"] == "MISSED"
            assert row["shared_capture_id"] is None
            assert row["shared_capture_complete"] == 0
            assert row["host_output_json"] is None
            assert row["hook_captured_at"] is None
            assert "hookCapture" not in json.loads(row["metadata_json"])
    else:
        for database in learning_root.glob("*/learning.sqlite"):
            with closing(sqlite3.connect(database)) as connection:
                assert connection.execute(
                    "SELECT COUNT(*) FROM learning_records"
                ).fetchone()[0] == 0


def test_duplicate_skill_invocations_are_rejected_before_hook_capture(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "cursor", home=home)
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-duplicate")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-duplicate")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    second = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    database = fallback(forge_root, project_root, first, "first fallback")
    fallback(forge_root, project_root, second, "second fallback")

    result = handle_host_event(
        forge_root, "cursor", "after-agent-response", {
            "workspace_roots": [str(project_root)],
            "conversation_id": "conversation-duplicate",
            "generation_id": "generation-duplicate",
            "text": "one response for duplicate Skill invocations",
        }, hook_home=home,
    )

    assert result["handled"] is False
    assert result["reason"] == "DUPLICATE_SKILL_INVOCATIONS"
    assert set(result["invocationIds"]) == {
        first["invocationId"], second["invocationId"],
    }
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert list(invocation_dir.glob("inv-*.json")) == []
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(
            "SELECT hook_status, host_output_json, shared_capture_id "
            "FROM learning_records ORDER BY invocation_id"
        ).fetchall()
    assert rows == [("MISSED", None, None), ("MISSED", None, None)]


def test_shared_hook_turn_over_database_limit_is_skipped_before_capture(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    skills = [f"skill-{index}" for index in range(12)]
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": skills,
    }), encoding="utf-8")
    configure_global_hook(forge_root, "cursor", home=tmp_path / "home")
    monkeypatch.setenv("CURSOR_CONVERSATION_ID", "conversation-limit")
    monkeypatch.setenv("CURSOR_GENERATION_ID", "generation-limit")
    invocations = [
        begin_invocation(forge_root, project_root, skill, hook_home=tmp_path / "home")
        for skill in skills
    ]

    result = handle_host_event(
        forge_root, "cursor", "after-agent-response", {
            "workspace_roots": [str(project_root)],
            "conversation_id": "conversation-limit",
            "generation_id": "generation-limit",
            "text": "one response for too many skills",
        }, hook_home=tmp_path / "home",
    )

    assert result["handled"] is False
    assert result["reason"] == "SHARED_GROUP_TOO_LARGE"
    assert result["count"] == 12
    assert result["maximum"] == learning_invocations.MAX_SHARED_CAPTURE_DATABASES
    assert set(result["invocationIds"]) == {
        invocation["invocationId"] for invocation in invocations
    }
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / invocations[0]["projectId"]
        / "learning" / "invocations"
    )
    assert list(invocation_dir.glob("inv-*.json")) == []


def test_identity_match_ignores_an_unrelated_pending_marker(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "codex", home=tmp_path / "home")
    monkeypatch.setenv("CODEX_SESSION_ID", "matching-session")
    matching = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    monkeypatch.delenv("CODEX_SESSION_ID")
    unrelated = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")

    handled = handle_host_event(
        forge_root, "codex", "stop",
        {
            "cwd": str(project_root),
            "session_id": "matching-session",
            "last_assistant_message": "matched response",
        },
        hook_home=tmp_path / "home",
    )

    assert handled["invocationId"] == matching["invocationId"]
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / matching["projectId"]
        / "learning" / "invocations"
    )
    remaining = [json.loads(path.read_text(encoding="utf-8")) for path in invocation_dir.glob("inv-*.json")]
    assert [marker["invocationId"] for marker in remaining] == [unrelated["invocationId"]]
    assert remaining[0]["status"] == "PENDING"


def test_session_only_identity_never_merges_multiple_host_turns(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "codex", home=tmp_path / "home")
    monkeypatch.setenv("CODEX_SESSION_ID", "shared-session")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    second = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")

    handled = handle_host_event(
        forge_root, "codex", "stop",
        {
            "cwd": str(project_root),
            "session_id": "shared-session",
            "turn_id": "turn-1",
            "last_assistant_message": "not safely attributable",
        },
        hook_home=tmp_path / "home",
    )

    assert handled == {"handled": False, "reason": "AMBIGUOUS_INVOCATION", "count": 2}
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert {path.stem for path in invocation_dir.glob("inv-*.json")} == {
        first["invocationId"], second["invocationId"],
    }


def test_claude_session_only_identity_keeps_multiple_skills_ambiguous(
    tmp_path, monkeypatch,
):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    config = project_root / ".forge-skill" / "learning" / "config.json"
    config.write_text(json.dumps({
        "schemaVersion": "1.0", "enabledSkills": ["code-review", "plan"],
    }), encoding="utf-8")
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "claude-shared-session")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=home)
    second = begin_invocation(forge_root, project_root, "plan", hook_home=home)

    handled = handle_host_event(
        forge_root, "claude-code", "stop", {
            "cwd": str(project_root),
            "session_id": "claude-shared-session",
            "last_assistant_message": "not safely attributable",
        }, hook_home=home,
    )

    assert handled == {
        "handled": False, "reason": "AMBIGUOUS_INVOCATION", "count": 2,
    }
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert {path.stem for path in invocation_dir.glob("inv-*.json")} == {
        first["invocationId"], second["invocationId"],
    }


def test_ambiguous_pending_invocations_keep_independent_fallbacks(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    configure_global_hook(forge_root, "codex", home=tmp_path / "home")
    first = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    second = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    database = fallback(forge_root, project_root, first, "first fallback")
    fallback(forge_root, project_root, second, "second fallback")

    handled = handle_host_event(
        forge_root,
        "codex",
        "stop",
        {"cwd": str(project_root), "last_assistant_message": "ambiguous combined response"},
        hook_home=tmp_path / "home",
    )

    assert handled == {"handled": False, "reason": "AMBIGUOUS_INVOCATION", "count": 2}
    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(
            "SELECT output_json, capture_source, hook_status FROM learning_records ORDER BY output_json"
        ).fetchall()
    assert len(rows) == 2
    assert {json.loads(row[0])["conclusion"] for row in rows} == {
        "first fallback", "second fallback",
    }
    assert all(row[1:] == ("SKILL_CONTRACT", "PENDING") for row in rows)
    invocation_dir = (
        forge_root.parent / "forge-data" / "projects" / first["projectId"]
        / "learning" / "invocations"
    )
    assert {path.stem for path in invocation_dir.glob("inv-*.json")} == {
        first["invocationId"], second["invocationId"],
    }


def test_without_configured_hook_invocation_still_supports_skill_fallback(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)

    invocation = begin_invocation(forge_root, project_root, "code-review", hook_home=tmp_path / "home")
    database = fallback(forge_root, project_root, invocation, "fallback only")

    assert invocation["hookExpected"] is False
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT capture_source, hook_status FROM learning_records"
        ).fetchone()
    assert row == ("SKILL_CONTRACT", "NOT_CONFIGURED")


def test_hook_event_resolves_project_from_nested_working_directory(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    nested = project_root / "src" / "feature"
    nested.mkdir(parents=True)
    configure_global_hook(forge_root, "claude-code", home=tmp_path / "home")
    invocation = begin_invocation(
        forge_root, project_root, "code-review", hook_home=tmp_path / "home"
    )
    database = fallback(forge_root, project_root, invocation, "fallback")

    handled = handle_host_event(
        forge_root,
        "claude-code",
        "stop",
        {"cwd": str(nested), "last_assistant_message": "nested result"},
        hook_home=tmp_path / "home",
    )

    assert handled["action"] == "CAPTURED"
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT output_json, host_output_json FROM learning_records"
        ).fetchone()
    assert json.loads(row[0]) == {"conclusion": "fallback"}
    assert json.loads(row[1]) == {"finalResponse": "nested result"}


def test_global_hook_status_reports_configured_hosts_and_installation(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)

    status = global_hook_status(forge_root, home=home)

    assert status["configuredHosts"] == ["codex"]
    assert status["configuredReady"] is True
    assert status["hosts"]["codex"]["managed"] is True
    assert status["hosts"]["codex"]["state"] == "CONFIGURED"
    assert status["hosts"]["codex"]["configState"] == "CONFIGURED"
    assert status["hosts"]["codex"]["runtimeState"] == "NEVER_OBSERVED"
    assert status["hosts"]["codex"]["eventScope"] == "NONE"
    assert status["hosts"]["codex"]["enabledStatus"] == "UNVERIFIED"
    assert status["hosts"]["codex"]["trustStatus"] == "MANUAL_CHECK_REQUIRED"
    assert status["hosts"]["claude-code"]["state"] == "NOT_CONFIGURED"
    assert status["hosts"]["claude-code"]["enabledStatus"] == "NOT_APPLICABLE"
    assert status["hosts"]["claude-code"]["trustStatus"] == "NOT_APPLICABLE"


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"host": "codex", "timestamp": "2999-01-01T00:00:00Z", "outcome": "CAPTURED"}, "HEALTHY"),
        ({"host": "codex", "timestamp": "2000-01-01T00:00:00Z", "outcome": "CAPTURED"}, "STALE"),
        ({"host": "codex", "timestamp": "2999-01-01T00:00:00Z", "outcome": "FAILED"}, "ERROR"),
    ],
)
def test_global_hook_status_reports_per_host_runtime_state(tmp_path, event, expected):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    state_path = hook_state_path(forge_root)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["hosts"]["codex"]["installedAt"] = "1999-01-01T00:00:00Z"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    path = hook_event_status_path(forge_root, "codex")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event), encoding="utf-8")

    status = global_hook_status(forge_root, home=home)

    assert status["hosts"]["codex"]["runtimeState"] == expected
    assert status["hosts"]["codex"]["eventScope"] == "CURRENT_INSTALLATION"
    assert status["hosts"]["claude-code"]["runtimeState"] == "NEVER_OBSERVED"


def test_unconfigured_host_receipt_is_reported_as_historical(tmp_path):
    forge_root = bundle(tmp_path)
    path = hook_event_status_path(forge_root, "claude-code")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "host": "claude-code",
        "timestamp": "2999-01-01T00:00:00Z",
        "outcome": "CAPTURED",
        "invocationIds": ["inv-old"],
    }), encoding="utf-8")

    status = global_hook_status(forge_root, home=tmp_path / "home")

    assert status["hosts"]["claude-code"]["eventScope"] == "HISTORICAL"
    assert status["hosts"]["claude-code"]["runtimeState"] == "NEVER_OBSERVED"
    assert status["hosts"]["claude-code"]["lastEvent"]["invocationIds"] == ["inv-old"]


def test_old_hook_event_does_not_make_new_installation_healthy(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    path = hook_event_status_path(forge_root, "codex")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "host": "codex",
        "timestamp": "2000-01-01T00:00:00Z",
        "outcome": "CAPTURED",
    }), encoding="utf-8")

    status = global_hook_status(forge_root, home=home)

    assert status["hosts"]["codex"]["runtimeState"] == "NEVER_OBSERVED"


def test_global_hook_status_reports_repair_required_for_missing_runtime(tmp_path):
    forge_root = bundle(tmp_path)
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["pythonExecutable"] = str(tmp_path / "missing-python.exe")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    status = global_hook_status(forge_root, home=tmp_path / "home")

    assert status["configuredReady"] is False
    assert all(item["configState"] == "REPAIR_REQUIRED" for item in status["hosts"].values())


def test_hook_installation_root_is_used_in_installed_command(tmp_path):
    forge_root = bundle(tmp_path)
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["hookInstallationRoot"] = str(forge_root.parent)
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    configure_global_hook(forge_root, "codex", home=tmp_path / "home")

    config = json.loads((tmp_path / "home" / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = config["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert str(forge_root.parent / "forge") in command
    script = forge_root.parent / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    assert base64.b64encode(str(script).encode("utf-8")).decode("ascii") in command


def test_mismatched_hook_installation_root_is_rejected(tmp_path):
    forge_root = bundle(tmp_path)
    wrong = tmp_path / "wrong-installation"
    (wrong / "forge").mkdir(parents=True)
    (wrong / "skills" / "learning-collector").mkdir(parents=True)
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["hookInstallationRoot"] = str(wrong)
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    with pytest.raises(ValueError, match="does not point to this Forge installation"):
        configure_global_hook(forge_root, "codex", home=tmp_path / "home")


def test_reconfigure_replaces_stale_runtime_command(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    config_path = home / ".codex" / "hooks.json"
    before = config_path.read_text(encoding="utf-8")
    replacement = tmp_path / "replacement-python.exe"
    replacement.write_bytes(b"")
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["pythonExecutable"] = str(replacement)
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = configure_global_hook(forge_root, "codex", home=home)
    after = config_path.read_text(encoding="utf-8")
    command = json.loads(after)["hooks"]["Stop"][0]["hooks"][0]["command"]

    assert result["state"] == "CONFIGURED"
    assert base64.b64encode(str(replacement).encode("utf-8")).decode("ascii") in command
    assert before != after
    assert global_hook_status(forge_root, home=home)["configuredReady"] is True


def test_reconfigure_upgrades_legacy_timeout_only_drift(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    config_path = home / ".codex" / "hooks.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["hooks"]["Stop"][0]["hooks"][0]["timeoutSec"] = 2
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = configure_global_hook(forge_root, "codex", home=home)

    assert result["state"] == "CONFIGURED"
    updated = json.loads(config_path.read_text(encoding="utf-8"))
    assert updated["hooks"]["Stop"][0]["hooks"][0]["timeoutSec"] == 5


def test_reconfigure_moves_owned_hook_to_new_global_config_path(tmp_path):
    forge_root = bundle(tmp_path)
    old_home = tmp_path / "old-home"
    new_home = tmp_path / "new-home"
    configure_global_hook(forge_root, "codex", home=old_home)

    result = configure_global_hook(forge_root, "codex", home=new_home)

    old_config = json.loads((old_home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    new_config = json.loads((new_home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert result["state"] == "CONFIGURED"
    assert "hooks" not in old_config
    assert "Stop" in new_config["hooks"]
    assert load_hook_state(forge_root)["hosts"]["codex"]["configPath"] == str(
        new_home / ".codex" / "hooks.json"
    )


def test_state_write_failure_restores_previous_command(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    config_path = home / ".codex" / "hooks.json"
    before = config_path.read_bytes()
    replacement = tmp_path / "replacement-python.exe"
    replacement.write_bytes(b"")
    runtime_path = forge_root.parent / "forge-data" / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["pythonExecutable"] = str(replacement)
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    def fail_save(*_args, **_kwargs):
        raise OSError("simulated state failure")

    monkeypatch.setattr(hook_manager, "_save_hook_state", fail_save)
    with pytest.raises(OSError, match="simulated state failure"):
        configure_global_hook(forge_root, "codex", home=home)

    assert config_path.read_bytes() == before


def test_begin_does_not_expect_manually_removed_hook(tmp_path):
    forge_root = bundle(tmp_path)
    project_root = project(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    (home / ".codex" / "hooks.json").unlink()

    invocation = begin_invocation(
        forge_root, project_root, "code-review", hook_home=home
    )

    assert invocation["hookHost"] is None
    assert invocation["hookExpected"] is False


def test_reconfigure_reinstalls_manually_removed_hook(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)
    config_path = home / ".codex" / "hooks.json"
    config_path.unlink()

    result = configure_global_hook(forge_root, "codex", home=home)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert result["state"] == "CONFIGURED"
    assert "Stop" in config["hooks"]
    assert global_hook_status(forge_root, home=home)["configuredReady"] is True


def test_state_write_failure_rolls_back_new_target_hook(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)

    def fail_save(*_args, **_kwargs):
        raise OSError("simulated state failure")

    monkeypatch.setattr(hook_manager, "_save_hook_state", fail_save)
    with pytest.raises(OSError, match="simulated state failure"):
        configure_global_hook(forge_root, "cursor", home=home)

    cursor = json.loads((home / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert "hooks" not in cursor
    claude = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Stop" in claude["hooks"]


def test_configuring_another_host_never_uninstalls_existing_host(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    original = hook_manager.LearningHookProvider.uninstall
    uninstalled = []

    def observe_uninstall(self):
        uninstalled.append(self.host)
        return original(self)

    monkeypatch.setattr(hook_manager.LearningHookProvider, "uninstall", observe_uninstall)
    result = configure_global_hook(forge_root, "cursor", home=home)

    assert result["state"] == "CONFIGURED"
    assert uninstalled == []
    state = load_hook_state(forge_root)
    assert set(state["hosts"]) == {"claude-code", "cursor"}


def test_hook_script_persists_bounded_failure_diagnostic(tmp_path):
    forge_root = bundle(tmp_path)
    data_root = tmp_path / "diagnostic-data"
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    environment = dict(__import__("os").environ)
    environment["FORGE_DATA_ROOT"] = str(data_root)

    result = subprocess.run(
        [
            sys.executable, str(script), "--host", "codex", "--event", "stop",
            "--forge-hook-marker", "forge-learning-capture-v1",
            "--forge-root", str(forge_root),
        ],
        input=b"{invalid", capture_output=True, timeout=5, env=environment, check=False,
    )

    diagnostic = json.loads(
        (data_root / "hook-status" / "codex.json").read_text(encoding="utf-8")
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b"{}"
    assert diagnostic["outcome"] == "FAILED"
    assert diagnostic["errorType"] == "JSONDecodeError"
    assert "payload" not in diagnostic
    trace_path = data_root / "hook-status" / "codex.trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["step"] for entry in trace] == [
        "hook_invoked", "input_received", "hook_finished",
    ]
    assert len({entry["traceId"] for entry in trace}) == 1
    assert "{invalid" not in trace_path.read_text(encoding="utf-8")


def test_hook_script_cursor_decoder_accepts_one_compatible_json_document():
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    spec = importlib.util.spec_from_file_location("host_capture_hook_decoder_test", script)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    payload, mode = hook._decode_payload(
        b'{"text":"first line\nsecond line"}\x00', cursor_compatible=True
    )

    assert payload == {"text": "first line\nsecond line"}
    assert mode == "cursor-compatible"


def test_hook_script_cursor_decoder_rejects_trailing_content():
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    spec = importlib.util.spec_from_file_location("host_capture_hook_decoder_reject_test", script)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    with pytest.raises(json.JSONDecodeError):
        hook._decode_payload(b'{"text":"ok"} garbage', cursor_compatible=True)


def test_hook_status_persists_bounded_invocation_ids(tmp_path):
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    spec = importlib.util.spec_from_file_location("host_capture_hook_status_test", script)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    hook._write_status(
        tmp_path / "forge", "codex", "stop", "CAPTURED",
        invocation_ids=["inv-current", 3, "", "x" * 200],
    )

    status = json.loads(
        (tmp_path / "forge-data" / "hook-status" / "codex.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["invocationIds"] == ["inv-current", "x" * 128]


def test_cursor_stop_hook_accepts_transport_nul(tmp_path):
    forge_root = Path(__file__).parents[1]
    data_root = tmp_path / "diagnostic-data"
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    environment = dict(__import__("os").environ)
    environment["FORGE_DATA_ROOT"] = str(data_root)
    payload = json.dumps({
        "workspace_roots": [str(tmp_path / "missing-project")],
        "conversation_id": "conversation-1",
        "generation_id": "generation-1",
    }).encode("utf-8") + b"\x00"

    result = subprocess.run(
        [
            sys.executable, str(script), "--host", "cursor", "--event", "stop",
            "--forge-hook-marker", "forge-learning-capture-v1",
            "--forge-root", str(forge_root),
        ],
        input=payload, capture_output=True, timeout=5, env=environment, check=False,
    )

    trace_path = data_root / "hook-status" / "cursor.trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    decoded = next(entry for entry in trace if entry["step"] == "payload_decoded")
    assert result.returncode == 0
    assert decoded["decodeMode"] == "cursor-compatible"
    assert trace[-1]["outcome"] == "SKIPPED"
    assert "errorType" not in trace[-1]


def test_hook_script_records_invocation_before_reading_input(tmp_path):
    forge_root = bundle(tmp_path)
    data_root = tmp_path / "diagnostic-data"
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    environment = dict(__import__("os").environ)
    environment["FORGE_DATA_ROOT"] = str(data_root)
    status_path = data_root / "hook-status" / "codex.json"
    trace_path = data_root / "hook-status" / "codex.trace.jsonl"
    process = subprocess.Popen(
        [
            sys.executable, str(script), "--host", "codex", "--event", "stop",
            "--forge-hook-marker", "forge-learning-capture-v1",
            "--forge-root", str(forge_root),
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        deadline = time.monotonic() + 5
        while not status_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert status_path.is_file()
        assert json.loads(status_path.read_text(encoding="utf-8"))["outcome"] == "INVOKED"
        assert json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])["step"] == "hook_invoked"
        stdout, stderr = process.communicate(input=b"", timeout=5)
        assert process.returncode == 0, stderr
        assert stdout.strip() == b"{}"
        final = json.loads(status_path.read_text(encoding="utf-8"))
        assert final["outcome"] == "SKIPPED"
        assert final["detail"] == "EmptyInput"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def test_hook_trace_is_trimmed_on_complete_json_line(tmp_path, monkeypatch):
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    spec = importlib.util.spec_from_file_location("host_capture_hook_for_test", script)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    data_root = tmp_path / "diagnostic-data"
    forge_root = tmp_path / "bundle" / "forge"
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data_root))
    monkeypatch.setattr(hook, "TRACE_MAX_BYTES", 1_200)
    monkeypatch.setattr(hook, "TRACE_RETAIN_BYTES", 800)

    for index in range(40):
        hook._write_trace(
            forge_root, "codex", f"trace-{index}", "hook_finished",
            file_lock=_registry_file_lock, outcome="SKIPPED", sequence=index,
        )

    trace_path = data_root / "hook-status" / "codex.trace.jsonl"
    content = trace_path.read_bytes()
    lines = content.splitlines()
    decoded = [json.loads(line.decode("utf-8")) for line in lines]

    assert len(content) <= hook.TRACE_MAX_BYTES
    assert all(line.startswith(b"{") for line in lines)
    assert decoded[-1]["sequence"] == 39


def test_hook_trace_skips_write_when_diagnostic_lock_times_out(tmp_path, monkeypatch):
    script = (
        Path(__file__).parents[2]
        / "skills" / "learning-collector" / "scripts" / "host_capture_hook.py"
    )
    spec = importlib.util.spec_from_file_location("host_capture_hook_timeout_test", script)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    data_root = tmp_path / "diagnostic-data"
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data_root))

    @contextmanager
    def timeout_lock(_path):
        raise TimeoutError("busy")
        yield

    written = hook._write_trace(
        tmp_path / "bundle" / "forge", "codex", "trace-timeout", "hook_invoked",
        file_lock=timeout_lock,
    )

    assert written is False
    assert not (data_root / "hook-status" / "codex.trace.jsonl").exists()
