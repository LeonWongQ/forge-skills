"""Regression tests for the Codex Hook diagnostic Skill."""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).parents[2]
    / "skills" / "hook-doctor" / "codex-hook-doctor"
    / "scripts" / "inspect_codex_hook.py"
)
SPEC = importlib.util.spec_from_file_location("inspect_codex_hook", SCRIPT)
assert SPEC and SPEC.loader
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


def configured_layers(**changes):
    layers = {
        "configured": True,
        "selected": True,
        "enabled": True,
        "trusted": True,
        "invoked": True,
        "captured": False,
        "capturedPreviously": False,
    }
    layers.update(changes)
    return layers


def test_matching_trace_and_learning_record_are_current_capture():
    trace = {"outcome": "CAPTURED", "invocationIds": ["inv-matching"]}
    record = {"hook_status": "CAPTURED", "invocation_id": "inv-matching"}

    capture = doctor._capture_layers(trace, record)

    assert capture == {"captured": True, "capturedPreviously": True}
    assert doctor._assessment(
        configured_layers(**capture), {"enabled": True}, trace
    ) == "CAPTURED"


def test_latest_no_pending_trace_preserves_only_previous_capture():
    trace = {"outcome": "SKIPPED", "reason": "NO_PENDING_INVOCATION", "invocationIds": []}
    record = {"hook_status": "CAPTURED", "invocation_id": "inv-earlier"}

    capture = doctor._capture_layers(trace, record)

    assert capture == {"captured": False, "capturedPreviously": True}
    assert doctor._assessment(
        configured_layers(**capture), {"enabled": True}, trace
    ) == "PREVIOUSLY_CAPTURED"


def test_mismatched_trace_and_learning_record_are_not_reported_as_captured():
    trace = {"outcome": "CAPTURED", "invocationIds": ["inv-trace"]}
    record = {"hook_status": "CAPTURED", "invocation_id": "inv-record"}

    capture = doctor._capture_layers(trace, record)

    assert capture == {"captured": False, "capturedPreviously": True}
    assert doctor._assessment(
        configured_layers(**capture), {"enabled": True}, trace
    ) == "CAPTURE_EVIDENCE_MISMATCH"


def test_capture_from_before_current_installation_is_not_current():
    trace = {
        "timestamp": "2026-01-01T00:00:00Z",
        "outcome": "CAPTURED",
        "invocationIds": ["inv-old"],
    }
    record = {"hook_status": "CAPTURED", "invocation_id": "inv-old"}
    current = doctor._at_or_after_installation(trace, "2026-01-02T00:00:00Z")

    capture = doctor._capture_layers(trace, record, current_installation_observed=current)

    assert current is False
    assert capture == {"captured": False, "capturedPreviously": True}
    assert doctor._assessment(
        configured_layers(invoked=False, **capture), {"enabled": True}, trace,
    ) == "NEVER_INVOKED"


def test_trace_from_current_installation_is_current():
    trace = {"timestamp": "2026-01-02T00:00:00Z"}

    assert doctor._at_or_after_installation(trace, "2026-01-01T00:00:00Z") is True


def test_missing_or_invalid_installation_timestamp_is_unknown():
    trace = {"timestamp": "2026-01-02T00:00:00Z"}

    assert doctor._at_or_after_installation(trace, None) is None
    assert doctor._at_or_after_installation(trace, "not-a-timestamp") is None
    assert doctor._assessment(
        configured_layers(invoked=None, captured=None), {"enabled": True}, trace,
        installation_verified=False,
    ) == "STATUS_UNKNOWN"


@pytest.mark.parametrize("installed_at", ["2026-01-01", "2026-01-01T00:00:00"])
def test_installation_timestamp_requires_full_timezone_aware_datetime(installed_at):
    trace = {"timestamp": "2026-01-02T00:00:00Z"}

    assert doctor._at_or_after_installation(trace, installed_at) is None


def test_trace_timestamp_requires_timezone():
    trace = {"timestamp": "2026-01-02T00:00:00"}

    assert doctor._at_or_after_installation(trace, "2026-01-01T00:00:00Z") is None


def test_invalid_identity_precedes_disabled_or_untrusted_hook_state():
    assert doctor._assessment(
        configured_layers(enabled=False, trusted=False, invoked=None, captured=None),
        {"enabled": False}, None, identity_verified=False,
    ) == "STATUS_UNKNOWN"


def test_capture_layers_preserve_unverified_evidence():
    assert doctor._capture_layers(None, None, None) == {
        "captured": None,
        "capturedPreviously": False,
    }
    assert doctor._capture_layers(
        None, None, False, identity_verified=False,
    ) == {"captured": None, "capturedPreviously": None}


def test_native_hook_layers_preserve_missing_or_unknown_fields():
    assert doctor._native_hook_layers(None) == (None, None)
    assert doctor._native_hook_layers({}) == (None, None)
    assert doctor._native_hook_layers({
        "enabled": "true", "trustStatus": "future-status",
    }) == (None, None)
    assert doctor._assessment(
        configured_layers(enabled=None), {"enabled": None}, None,
    ) == "STATUS_UNKNOWN"
    assert doctor._assessment(
        configured_layers(trusted=None), {"enabled": True}, None,
    ) == "STATUS_UNKNOWN"


def test_native_hook_layers_decode_known_values():
    assert doctor._native_hook_layers({
        "enabled": True, "trustStatus": "managed",
    }) == (True, True)
    assert doctor._native_hook_layers({
        "enabled": False, "trustStatus": "modified",
    }) == (False, False)


def _write_project_identity_and_registry(
    tmp_path: Path, project_id: str, registered_project: Path | None = None,
):
    forge_root = tmp_path / "install" / "forge"
    project = tmp_path / "workspace"
    identity_dir = project / ".forge-skill" / "learning"
    registry_dir = forge_root.parent / "forge-data"
    identity_dir.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    (identity_dir / "project.json").write_text(
        json.dumps({"projectId": project_id}), encoding="utf-8"
    )
    (registry_dir / "project-registry.json").write_text(
        json.dumps({"projects": [{
            "projectId": project_id,
            "path": str(registered_project or project),
        }]}),
        encoding="utf-8",
    )
    return forge_root, project


def test_project_identity_requires_valid_id_and_matching_registry_path(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(tmp_path, project_id)

    assert doctor._project_id(forge_root, project) == project_id


def test_project_identity_rejects_malformed_or_traversal_id(tmp_path):
    forge_root, project = _write_project_identity_and_registry(
        tmp_path, "project-../../outside"
    )

    assert doctor._project_id(forge_root, project) is None


def test_project_identity_rejects_registry_path_for_another_project(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(
        tmp_path, project_id, tmp_path / "copied-workspace"
    )

    assert doctor._project_id(forge_root, project) is None


def test_latest_captured_record_is_limited_to_codex_host(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(tmp_path, project_id)
    database_dir = (
        forge_root.parent / "forge-data" / "projects" / project_id / "learning" / "code-review"
    )
    database_dir.mkdir(parents=True)
    database = database_dir / "learning.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "CREATE TABLE learning_records ("
            "invocation_id TEXT, skill TEXT, capture_source TEXT, hook_host TEXT, "
            "hook_status TEXT, captured_at TEXT, hook_captured_at TEXT)"
        )
        connection.executemany(
            "INSERT INTO learning_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("inv-codex", "code-review", "hook", "codex", "CAPTURED",
                 "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                ("inv-claude", "code-review", "hook", "claude", "CAPTURED",
                 "2026-01-02T00:00:00Z", "2026-01-02T00:00:00Z"),
            ],
        )
        connection.commit()

    latest, captured, errors = doctor._latest_records(forge_root, project, project_id)

    assert latest["invocation_id"] == "inv-claude"
    assert captured["invocation_id"] == "inv-codex"
    assert captured["hook_host"] == "codex"
    assert errors == []


def test_latest_records_surfaces_invalid_database(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(tmp_path, project_id)
    database = (
        forge_root.parent / "forge-data" / "projects" / project_id
        / "learning" / "broken" / "learning.sqlite"
    )
    database.parent.mkdir(parents=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")

    latest, captured, errors = doctor._latest_records(forge_root, project, project_id)

    assert latest is None
    assert captured is None
    assert errors == [{"database": str(database), "errorType": "OperationalError"}]
    assert doctor._assessment(
        configured_layers(), {"enabled": True},
        {"outcome": "CAPTURED", "complete": True}, learning_verified=False,
    ) == "STATUS_UNKNOWN"


def test_latest_records_reads_pre_hook_schema_without_reporting_database_error(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(tmp_path, project_id)
    database = (
        forge_root.parent / "forge-data" / "projects" / project_id
        / "learning" / "explain" / "learning.sqlite"
    )
    database.parent.mkdir(parents=True)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "CREATE TABLE learning_records (skill TEXT, captured_at TEXT)"
        )
        connection.execute(
            "INSERT INTO learning_records VALUES ('explain', '2026-01-03T00:00:00Z')"
        )

    latest, captured, errors = doctor._latest_records(forge_root, project, project_id)

    assert latest == {
        "invocation_id": None,
        "skill": "explain",
        "capture_source": "RUNTIME",
        "hook_host": None,
        "hook_status": "NOT_EXPECTED",
        "captured_at": "2026-01-03T00:00:00Z",
        "hook_captured_at": None,
    }
    assert captured is None
    assert errors == []


def test_latest_records_preserves_valid_data_when_another_database_fails(tmp_path):
    project_id = "project-7ae4d73f-be19-467f-aebd-f068e104fa1a"
    forge_root, project = _write_project_identity_and_registry(tmp_path, project_id)
    learning_root = (
        forge_root.parent / "forge-data" / "projects" / project_id / "learning"
    )
    valid = learning_root / "code-review" / "learning.sqlite"
    valid.parent.mkdir(parents=True)
    with closing(sqlite3.connect(valid)) as connection:
        connection.execute(
            "CREATE TABLE learning_records ("
            "invocation_id TEXT, skill TEXT, capture_source TEXT, hook_host TEXT, "
            "hook_status TEXT, captured_at TEXT, hook_captured_at TEXT)"
        )
        connection.execute(
            "INSERT INTO learning_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("inv-valid", "code-review", "hook", "codex", "CAPTURED",
             "2026-01-02T00:00:00Z", "2026-01-02T00:00:00Z"),
        )
        connection.commit()
    invalid = learning_root / "debug" / "learning.sqlite"
    invalid.parent.mkdir(parents=True)
    invalid.write_bytes(b"not a sqlite database")

    latest, captured, errors = doctor._latest_records(forge_root, project, project_id)

    assert latest["invocation_id"] == "inv-valid"
    assert captured["invocation_id"] == "inv-valid"
    assert errors == [{"database": str(invalid), "errorType": "DatabaseError"}]


def test_project_trace_controls_error_assessment():
    captured_trace = {"outcome": "CAPTURED", "invocationIds": ["inv-project"]}
    failed_trace = {"outcome": "FAILED", "invocationIds": []}

    assert doctor._assessment(
        configured_layers(captured=True, capturedPreviously=True),
        {"enabled": True}, captured_trace,
    ) == "CAPTURED"
    assert doctor._assessment(
        configured_layers(), {"enabled": True}, failed_trace,
    ) == "HOOK_ERROR"


def test_learning_failure_does_not_hide_proven_runtime_states():
    assert doctor._assessment(
        configured_layers(captured=True, capturedPreviously=True),
        {"enabled": True}, {"outcome": "CAPTURED"}, learning_verified=False,
    ) == "CAPTURED"
    assert doctor._assessment(
        configured_layers(), {"enabled": True},
        {"outcome": "FAILED"}, learning_verified=False,
    ) == "HOOK_ERROR"
    assert doctor._assessment(
        configured_layers(), {"enabled": True},
        {"outcome": None, "complete": False}, learning_verified=False,
    ) == "HOOK_IN_PROGRESS"


@pytest.mark.parametrize("layer", ["configured", "selected"])
def test_unknown_manager_layers_produce_status_unknown(layer):
    assert doctor._assessment(
        configured_layers(**{layer: None}), {"enabled": True}, None,
    ) == "STATUS_UNKNOWN"


def test_corrupt_hook_state_still_emits_structured_json(tmp_path):
    forge_root = SCRIPT.parents[4] / "forge"
    data_root = tmp_path / "forge-data"
    data_root.mkdir()
    (data_root / "learning-hooks.json").write_text("{invalid", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_text("not executable", encoding="utf-8")
    environment = dict(os.environ)
    environment["FORGE_DATA_ROOT"] = str(data_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(tmp_path),
         "--forge-root", str(forge_root), "--codex-executable", str(fake_codex)],
        capture_output=True, text=True, timeout=10, env=environment, check=False,
    )
    output = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert output["assessment"] == "STATUS_UNKNOWN"
    assert output["layers"]["configured"] is None
    assert output["layers"]["selected"] is None
    assert output["forge"]["managerError"]["errorType"] == "ValueError"
    assert output["runtime"]["stateError"]["errorType"] == "ValueError"


def test_common_status_names_are_used():
    assert doctor._assessment(configured_layers(), None, None) == "STATUS_UNKNOWN"
    assert doctor._assessment(
        configured_layers(), {"enabled": True}, {"outcome": "SKIPPED"}
    ) == "ACTIVE_NO_MATCH"


def test_latest_trace_is_scoped_to_requested_project(tmp_path):
    trace_path = tmp_path / "codex.trace.jsonl"
    events = [
        {"traceId": "wanted", "step": "project_resolution", "projectId": "project-a"},
        {"traceId": "wanted", "step": "invocation_match", "invocationIds": ["inv-a"]},
        {"traceId": "wanted", "step": "hook_finished", "outcome": "CAPTURED"},
        {"traceId": "other", "step": "project_resolution", "projectId": "project-b"},
        {"traceId": "other", "step": "hook_finished", "outcome": "SKIPPED"},
    ]
    trace_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    trace, error = doctor._latest_trace(trace_path, "project-a")

    assert error is None
    assert trace["traceId"] == "wanted"
    assert trace["invocationIds"] == ["inv-a"]
    assert trace["outcome"] == "CAPTURED"


def test_incomplete_latest_project_trace_is_reported_in_progress(tmp_path):
    trace_path = tmp_path / "codex.trace.jsonl"
    events = [
        {"traceId": "running", "step": "hook_invoked"},
        {"traceId": "running", "step": "project_resolution", "projectId": "project-a"},
    ]
    trace_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    trace, error = doctor._latest_trace(trace_path, "project-a")

    assert error is None
    assert trace["complete"] is False
    assert doctor._assessment(
        configured_layers(), {"enabled": True}, trace
    ) == "HOOK_IN_PROGRESS"


def test_latest_trace_reads_bounded_tail_and_skips_partial_or_malformed_lines(
    tmp_path, monkeypatch,
):
    trace_path = tmp_path / "codex.trace.jsonl"
    events = [
        {"traceId": "wanted", "step": "project_resolution", "projectId": "project-a"},
        {"traceId": "wanted", "step": "invocation_match", "invocationIds": ["inv-a"]},
        {"traceId": "wanted", "step": "hook_finished", "outcome": "CAPTURED"},
    ]
    suffix = b"{malformed}\n" + b"\n".join(
        json.dumps(event).encode("utf-8") for event in events
    )
    trace_path.write_bytes(b"x" * 600 + b"\n" + suffix)
    monkeypatch.setattr(doctor, "TRACE_TAIL_BYTES", len(suffix) + 20)

    trace, error = doctor._latest_trace(trace_path, "project-a")

    assert error is None
    assert trace["traceId"] == "wanted"
    assert trace["invocationIds"] == ["inv-a"]
    assert trace["outcome"] == "CAPTURED"


def test_latest_trace_uses_each_trace_last_event_for_interleaved_runs(tmp_path):
    trace_path = tmp_path / "codex.trace.jsonl"
    events = [
        {"traceId": "a", "step": "project_resolution", "projectId": "project-a"},
        {"traceId": "b", "step": "project_resolution", "projectId": "project-a"},
        {"traceId": "b", "step": "hook_finished", "outcome": "SKIPPED"},
        {"traceId": "a", "step": "hook_finished", "outcome": "CAPTURED"},
    ]
    trace_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    trace, error = doctor._latest_trace(trace_path, "project-a")

    assert error is None
    assert trace["traceId"] == "a"
    assert trace["outcome"] == "CAPTURED"


def test_invalid_trace_returns_structured_error_instead_of_never_invoked(tmp_path):
    trace_path = tmp_path / "codex.trace.jsonl"
    trace_path.write_text("not-json\n", encoding="utf-8")

    trace, error = doctor._latest_trace(trace_path, "project-a")
    relation = None if error else doctor._at_or_after_installation(
        trace, "2026-01-01T00:00:00Z"
    )

    assert trace is None
    assert error == {"path": str(trace_path), "errorType": "InvalidTrace"}
    assert doctor._assessment(
        configured_layers(invoked=relation, captured=None), {"enabled": True}, trace,
        installation_verified=relation is not None,
    ) == "STATUS_UNKNOWN"


def test_trace_read_failure_returns_structured_error():
    class UnreadableTrace:
        def open(self, _mode):
            raise PermissionError("denied")

        def __str__(self):
            return "unreadable.trace.jsonl"

    trace_path = UnreadableTrace()

    trace, error = doctor._latest_trace(trace_path, "project-a")

    assert trace is None
    assert error == {"path": str(trace_path), "errorType": "PermissionError"}


class FakeStdout:
    def __init__(self):
        self.lines = queue.Queue()
        self.read_started = threading.Event()

    def readline(self):
        self.read_started.set()
        return self.lines.get()


class FakeStdin:
    def __init__(self, on_flush):
        self.writes = []
        self.on_flush = on_flush

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        self.on_flush()


class FakeProcess:
    def __init__(self, producer, exit_code=None, wait_error=None):
        self.stdout = FakeStdout()
        self.stdin = FakeStdin(lambda: producer(self.stdout))
        self.exit_code = exit_code
        self.wait_error = wait_error
        self.killed = False

    def poll(self):
        return self.exit_code if self.exit_code is not None else (0 if self.killed else None)

    def kill(self):
        self.killed = True
        self.stdout.lines.put("")

    def wait(self, timeout):
        if self.wait_error is not None:
            raise self.wait_error
        return self.poll()


def run_hooks_list(monkeypatch, tmp_path, producer, exit_code=None, wait_error=None):
    process = FakeProcess(producer, exit_code=exit_code, wait_error=wait_error)
    monkeypatch.setattr(doctor.subprocess, "Popen", lambda *_args, **_kwargs: process)
    result = doctor._hooks_list(tmp_path / "codex.exe", tmp_path, timeout=1)
    return result, process


def test_notifications_before_delayed_hooks_response_are_not_lost(monkeypatch, tmp_path):
    def producer(stdout):
        def publish():
            assert stdout.read_started.wait(timeout=1)
            stdout.lines.put(json.dumps({"method": "hook/started"}) + "\n")
            stdout.lines.put(json.dumps({
                "id": 2,
                "result": {"data": [{
                    "cwd": str(tmp_path), "hooks": [{"key": "owned"}],
                }]},
            }) + "\n")

        threading.Thread(target=publish, daemon=True).start()

    (selected, error), process = run_hooks_list(monkeypatch, tmp_path, producer)

    assert error is None
    assert selected == {"cwd": str(tmp_path), "hooks": [{"key": "owned"}]}
    assert len(process.stdin.writes) == 3


def test_hooks_list_does_not_fall_back_to_another_workspace(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({
            "id": 2,
            "result": {"data": [
                {"cwd": str(tmp_path / "other-a"), "hooks": [{"key": "a"}]},
                {"cwd": str(tmp_path / "other-b"), "hooks": [{"key": "b"}]},
            ]},
        }) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert selected is None
    assert error == "hooks/list returned no entry for the requested project"


def test_hooks_list_accepts_one_explicit_global_group(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({
            "id": 2, "result": {"data": [{"hooks": [{"key": "global"}]}]},
        }) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert error is None
    assert selected == {"hooks": [{"key": "global"}]}


def test_hooks_list_rejects_invalid_hook_entries(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({
            "id": 2,
            "result": {"data": [{"cwd": str(tmp_path), "hooks": ["invalid"]}]},
        }) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert selected is None
    assert error == "hooks/list returned invalid hooks entries"


def test_hooks_list_path_matching_uses_host_case_semantics(monkeypatch, tmp_path):
    alternate_case = str(tmp_path).swapcase()
    if alternate_case == str(tmp_path):
        pytest.skip("temporary path has no cased characters")

    def producer(stdout):
        stdout.lines.put(json.dumps({
            "id": 2,
            "result": {"data": [{
                "cwd": alternate_case, "hooks": [{"key": "case-check"}],
            }]},
        }) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)
    paths_match = Path(alternate_case).resolve(strict=False) == tmp_path.resolve(strict=False)

    if paths_match:
        assert error is None
        assert selected is not None
    else:
        assert selected is None
        assert error == "hooks/list returned no entry for the requested project"


def test_app_server_protocol_error_is_surfaced(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({"id": 2, "error": {"code": -1, "message": "failed"}}) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert selected is None
    assert "failed" in error


def test_app_server_exit_before_response_is_bounded(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put("")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer, exit_code=7)

    assert selected is None
    assert error == "app-server exited before hooks/list response with exit code 7"


def test_malformed_stdout_does_not_hide_later_valid_response(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put("not-json\n")
        stdout.lines.put(json.dumps({
            "id": 2, "result": {"data": [{"cwd": str(tmp_path), "hooks": []}]},
        }) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert error is None
    assert selected == {"cwd": str(tmp_path), "hooks": []}


def test_valid_json_with_invalid_result_shape_is_surfaced(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({"id": 2, "result": None}) + "\n")

    (selected, error), _ = run_hooks_list(monkeypatch, tmp_path, producer)

    assert selected is None
    assert error == "hooks/list returned an invalid result object"


def test_app_server_launch_failure_is_surfaced(monkeypatch, tmp_path):
    def fail_launch(*_args, **_kwargs):
        raise OSError("launch denied")

    monkeypatch.setattr(doctor.subprocess, "Popen", fail_launch)

    selected, error = doctor._hooks_list(tmp_path / "codex.exe", tmp_path, timeout=1)

    assert selected is None
    assert error == "app-server launch failed: launch denied"


def test_app_server_wait_timeout_does_not_override_response(monkeypatch, tmp_path):
    def producer(stdout):
        stdout.lines.put(json.dumps({
            "id": 2, "result": {"data": [{"cwd": str(tmp_path), "hooks": []}]},
        }) + "\n")

    timeout = doctor.subprocess.TimeoutExpired("codex app-server", 5)
    (selected, error), _ = run_hooks_list(
        monkeypatch, tmp_path, producer, wait_error=timeout
    )

    assert error is None
    assert selected == {"cwd": str(tmp_path), "hooks": []}
