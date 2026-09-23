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
from forge_cli.learning_collector import _registry_file_lock, collect_imported_result
from forge_cli.learning_hook_manager import (
    configure_global_hook,
    global_hook_status,
    hook_event_status_path,
    hook_state_path,
    load_hook_state,
    remove_global_hook,
)
from forge_cli.learning_invocations import begin_invocation, handle_host_event
from forge_cli.runtime_paths import _project_id


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


def fallback(forge_root: Path, project_root: Path, invocation: dict, content: str) -> Path:
    envelope = {
        "runtime_id": f"direct.{invocation['invocationId']}",
        "resolved_context": {"selection": {"skill": "skill.code_review"}},
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


def test_switching_global_host_installs_target_and_removes_previous_hook(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"

    first = configure_global_hook(forge_root, "claude-code", home=home)
    switched = configure_global_hook(forge_root, "cursor", home=home)

    assert first["state"] == "CONFIGURED"
    assert switched["previousHost"] == "claude-code"
    assert switched["cleanup"] == {"claude-code": "NOT_CONFIGURED"}
    claude = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cursor = json.loads((home / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert "hooks" not in claude
    assert set(cursor["hooks"]) == {"afterAgentResponse", "stop"}
    state = json.loads(hook_state_path(forge_root).read_text(encoding="utf-8"))
    assert set(state["hosts"]) == {"cursor"}
    assert state["selectedHost"] == "cursor"


def test_removing_global_hook_clears_selection_and_owned_config(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    removed = remove_global_hook(forge_root, home=home)

    assert removed["selectedHost"] is None
    assert removed["cleanup"] == {"claude-code": "NOT_CONFIGURED"}
    claude = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "hooks" not in claude


def test_legacy_single_host_selection_migrates_to_global_semantics(tmp_path):
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

    assert state["schemaVersion"] == "2.0"
    assert state["selectedHost"] == "claude-code"


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
        "handler_entered", "project_resolution", "host_selection", "pending_lookup",
        "identity_check", "invocation_match", "response_check", "collection_started",
        "collection_finished",
    ]
    assert steps[5]["invocationIds"] == [invocation["invocationId"]]
    assert steps[-1]["stored"] is True
    trace_text = json.dumps(steps)
    assert "private-session" not in trace_text
    assert "private final response" not in trace_text
    assert str(project_root) not in trace_text


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
    for skill in ("code-review", "plan"):
        database = (
            forge_root.parent / "forge-data" / "projects" / first["projectId"]
            / "learning" / skill / "learning.sqlite"
        )
        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                "SELECT host_output_json, hook_status FROM learning_records"
            ).fetchone()
        assert json.loads(row[0]) == {"finalResponse": "shared host response"}
        assert row[1] == "CAPTURED"


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


def test_global_hook_status_reports_selected_host_and_installation(tmp_path):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "codex", home=home)

    status = global_hook_status(forge_root, home=home)

    assert status["selectedHost"] == "codex"
    assert status["hosts"]["codex"]["selected"] is True
    assert status["hosts"]["codex"]["state"] == "CONFIGURED"
    assert status["hosts"]["codex"]["configState"] == "CONFIGURED"
    assert status["hosts"]["codex"]["runtimeState"] == "NEVER_OBSERVED"
    assert status["hosts"]["claude-code"]["state"] == "NOT_CONFIGURED"


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
    path = hook_event_status_path(forge_root, "codex")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event), encoding="utf-8")

    status = global_hook_status(forge_root, home=tmp_path / "home")

    assert status["hosts"]["codex"]["runtimeState"] == expected
    assert status["hosts"]["claude-code"]["runtimeState"] == "NEVER_OBSERVED"


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

    assert status["selectedReady"] is False
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
    assert global_hook_status(forge_root, home=home)["selectedReady"] is True


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
    assert global_hook_status(forge_root, home=home)["selectedReady"] is True


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


def test_cleanup_failure_is_reported_as_partial_and_retained(tmp_path, monkeypatch):
    forge_root = bundle(tmp_path)
    home = tmp_path / "home"
    configure_global_hook(forge_root, "claude-code", home=home)
    original = hook_manager.LearningHookProvider.uninstall

    def fail_claude(self):
        if self.host == "claude-code":
            raise OSError("simulated cleanup failure")
        return original(self)

    monkeypatch.setattr(hook_manager.LearningHookProvider, "uninstall", fail_claude)
    result = configure_global_hook(forge_root, "cursor", home=home)

    assert result["state"] == "PARTIAL"
    assert result["cleanup"]["claude-code"].startswith("CLEANUP_FAILED")
    state = load_hook_state(forge_root)
    assert state["selectedHost"] == "cursor"
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
