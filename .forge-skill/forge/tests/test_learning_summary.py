from __future__ import annotations

import hashlib
import io
import json
import socket
import sqlite3
import sys
import threading
import urllib.error
from contextlib import closing, contextmanager
from types import SimpleNamespace
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "path", [
        "/", "/api/service", "/api/records", "/api/projects",
        "/api/summary-generation", "/api/summary-generation-estimate",
    ]
)
def test_get_rejects_rebinding_host_before_serving_data(path):
    handler = object.__new__(review_server.Handler)
    handler.path = path
    handler.headers = {"Host": "attacker.example:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    handler.do_GET()
    assert responses == [({"error": "invalid service host"}, 403)]


def test_get_service_probe_accepts_loopback_host():
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/service"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    handler.do_GET()
    assert responses[0][1] == 200
    assert responses[0][0]["token"] == review_server.SERVICE_TOKEN


@pytest.mark.parametrize("fails", [False, True])
def test_overlay_evaluation_reservation_blocks_duplicate_and_releases_on_completion(monkeypatch, fails):
    entered, release = threading.Event(), threading.Event()
    results = []
    payload = {"projectId": "project", "skill": "code-review", "overlayId": "one"}

    def evaluate(value):
        if value["overlayId"] == "other":
            return {"status": "PUBLISHED"}
        entered.set()
        assert release.wait(5)
        if fails:
            raise ValueError("evaluation failed")
        return {"status": "PUBLISHED"}

    monkeypatch.setattr(review_server, "_evaluate_and_publish_overlay", evaluate)

    def worker():
        try:
            results.append(review_server.evaluate_and_publish_overlay(payload))
        except ValueError as error:
            results.append(str(error))

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert entered.wait(5)
        with pytest.raises(ValueError, match="already running"):
            review_server.evaluate_and_publish_overlay({**payload, "skill": "skill.code_review"})
        assert review_server.evaluate_and_publish_overlay({**payload, "overlayId": "other"}) == {"status": "PUBLISHED"}
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert results == ["evaluation failed" if fails else {"status": "PUBLISHED"}]
    monkeypatch.setattr(review_server, "_evaluate_and_publish_overlay", lambda _value: {"status": "PUBLISHED"})
    assert review_server.evaluate_and_publish_overlay(payload) == {"status": "PUBLISHED"}


def test_summary_generation_get_distinguishes_missing_job_from_service_error(monkeypatch):
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/summary-generation?project=project&skill=plan"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))

    def missing(_query):
        raise review_server.SummaryJobNotFound("Summary generation job not found")

    monkeypatch.setattr(review_server, "get_summary_generation", missing)
    handler.do_GET()
    assert responses == [({"error": "Summary generation job not found", "code": "SUMMARY_JOB_NOT_FOUND"}, 404)]

    def unavailable(_query):
        raise OSError("status unavailable")

    responses.clear()
    monkeypatch.setattr(review_server, "get_summary_generation", unavailable)
    handler.do_GET()
    assert responses[0][1] == 500
    assert "code" not in responses[0][0]


def test_summary_submission_get_has_distinct_unknown_outcome_code(monkeypatch):
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/summary-generation?project=project&skill=plan&submission=not-yet-registered"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    monkeypatch.setattr(review_server, "_summary_generation_scope", lambda *args, **kwargs: ({}, Path("unused"), "plan"))
    captured = {}

    def missing(_database, **kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(review_server, "summary_job_status", missing)
    handler.do_GET()
    assert responses[0][1] == 404
    assert responses[0][0]["code"] == "SUMMARY_SUBMISSION_NOT_FOUND"
    assert captured["submission_id"] == "not-yet-registered"


def test_summary_submission_is_registered_before_llm_setup_failure(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    monkeypatch.setattr(review_server, "_summary_generation_scope", lambda *args, **kwargs: ({}, database, "plan"))

    def unavailable():
        status = review_server.summary_job_status(database, submission_id="setup-failure")
        assert status["status"] == "PREPARING"
        raise ValueError("LLM not configured")

    monkeypatch.setattr(review_server, "_summary_llm", unavailable)
    with pytest.raises(ValueError, match="LLM not configured"):
        review_server.start_summary_generation({
            "projectId": "project", "skill": "plan", "submissionId": "setup-failure",
        })
    status = review_server.get_summary_generation({
        "project": ["project"], "skill": ["plan"], "submission": ["setup-failure"],
    })
    assert status["status"] == "FAILED" and status["retryable"] is False
    assert review_server.start_summary_generation({
        "projectId": "project", "skill": "plan", "submissionId": "setup-failure",
    })["status"] == "FAILED"
    monkeypatch.setattr(review_server, "_summary_generation_scope", lambda *args, **kwargs: ({}, database, "debug"))
    with pytest.raises(review_server.SummarySubmissionNotFound):
        review_server.get_summary_generation({
            "project": ["project"], "skill": ["debug"], "submission": ["setup-failure"],
        })


def test_summary_submission_generate_and_retry_api_link_receipts_to_one_job_each(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    with connection:
        connection.execute(
            "INSERT INTO learning_records "
            "(id, project_id, project_name, project_path, skill, captured_at, output_json, reviewed, review_status, capture_source) "
            "VALUES ('source', 'project', 'project', ?, 'plan', ?, ?, 1, 'ACTIVE', 'SKILL_CONTRACT')",
            (str(tmp_path), review_server.now(), json.dumps({"objective": "Verify dependencies"})),
        )
    connection.close()
    monkeypatch.setattr(review_server, "_summary_generation_scope", lambda *args, **kwargs: ({}, database, "plan"))
    monkeypatch.setattr(review_server, "_skill_text", lambda _skill: "# Plan")
    monkeypatch.setattr(threading.Thread, "start", lambda _thread: None)
    calls = []

    def configured():
        calls.append("config")
        return {"model": "test", "baseUrl": "https://example.test/v1", "wireApi": "responses"}, lambda *_args: None

    monkeypatch.setattr(review_server, "_summary_llm", configured)
    payload = {"projectId": "project", "skill": "plan", "submissionId": "generate-once"}
    first = review_server.start_summary_generation(payload)
    duplicate = review_server.start_summary_generation(payload)
    assert first["jobId"] == duplicate["jobId"]
    assert calls == ["config"]
    assert review_server.get_summary_generation({
        "project": ["project"], "skill": ["plan"], "submission": ["generate-once"],
    })["jobId"] == first["jobId"]
    assert review_server.interrupt_stale_jobs(database) == 1
    retry_payload = {**payload, "submissionId": "retry-once", "jobId": first["jobId"]}
    retry = review_server.retry_summary_generation(retry_payload)
    assert retry["jobId"] != first["jobId"]
    assert review_server.retry_summary_generation(retry_payload)["jobId"] == retry["jobId"]
    assert calls == ["config", "config"]
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_submissions WHERE status = 'ACCEPTED'").fetchone()[0] == 2
    connection.close()


def test_summary_generation_estimate_get_routes_query(monkeypatch):
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/summary-generation-estimate?project=project&skill=plan&language=en"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    monkeypatch.setattr(
        review_server, "get_summary_generation_estimate",
        lambda query: {"project": query["project"][0], "skill": query["skill"][0]},
    )

    handler.do_GET()

    assert responses == [({"project": "project", "skill": "plan"}, 200)]


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/api/summary-generation", "start_summary_generation"),
        ("/api/summary-generation-retry", "retry_summary_generation"),
    ],
)
def test_summary_generation_mutations_return_accepted(monkeypatch, path, target):
    payload = {"projectId": "project", "skill": "plan"}
    body = json.dumps(payload).encode()
    handler = object.__new__(review_server.Handler)
    handler.path = path
    handler.headers = {
        "Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765",
        "Content-Type": "application/json", "Content-Length": str(len(body)),
        "Cookie": f"{review_server.SERVICE_COOKIE}=test-token",
    }
    handler.server = SimpleNamespace(server_port=8765)
    handler.rfile = io.BytesIO(body)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    monkeypatch.setattr(review_server, "SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(
        review_server, target,
        lambda value: {"jobId": "job", "status": "PENDING", "request": value},
    )

    handler.do_POST()

    assert responses == [({"jobId": "job", "status": "PENDING", "request": payload}, 202)]


@pytest.mark.parametrize("path", ["/api/refine", "/api/summarize"])
def test_retired_summary_mutation_paths_return_not_found(path):
    handler = object.__new__(review_server.Handler)
    handler.path = path
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))

    handler.do_POST()

    assert responses == [({"error": "not found"}, 404)]


def test_copy_overlay_endpoint_creates_a_draft(monkeypatch):
    payload = {"projectId": "project", "skill": "plan", "overlayId": "overlay-1"}
    body = json.dumps(payload).encode()
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/copy-overlay"
    handler.headers = {
        "Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765",
        "Content-Type": "application/json", "Content-Length": str(len(body)),
        "Cookie": f"{review_server.SERVICE_COOKIE}=test-token",
    }
    handler.server = SimpleNamespace(server_port=8765)
    handler.rfile = io.BytesIO(body)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    monkeypatch.setattr(review_server, "SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(
        review_server, "copy_overlay",
        lambda value: {"id": "overlay-2", "status": "DRAFT", "request": value},
    )

    handler.do_POST()

    assert responses == [({"id": "overlay-2", "status": "DRAFT", "request": payload}, 201)]


@pytest.mark.parametrize("operation", ["overlay", "summary", "record"])
def test_mutation_guards_hold_write_lock_before_read(tmp_path, monkeypatch, operation):
    database = tmp_path / "guard.sqlite"
    connection = connect_database(database)
    with connection:
        connection.execute(
            "INSERT INTO learning_records (id, project_id, project_name, project_path, skill, captured_at, output_json) "
            "VALUES ('record', 'project-lock', 'project', ?, 'code-review', '2026-09-17T00:00:00Z', '{}')",
            (str(tmp_path),),
        )
        connection.execute(
            "INSERT INTO learning_summaries (id, project_id, skill, version, created_at, source_count, summary_json) "
            "VALUES ('summary', 'project-lock', 'code-review', 1, 'now', 0, '{}')"
        )
        connection.execute(
            "INSERT INTO skill_overlays (id, project_id, skill, version, status, content, manifest_json, content_digest, created_at) "
            "VALUES ('overlay', 'project-lock', 'code-review', 1, 'DRAFT', 'content', '{}', 'digest', 'now')"
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": "project-lock", "name": "project", "path": str(tmp_path), "database": str(database),
    }])
    original_connect = review_server.connect_database
    blocked = []

    def guarded_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)

        def trace(sql):
            if not sql.lstrip().upper().startswith("SELECT") or blocked:
                return
            other = sqlite3.connect(database, timeout=0)
            try:
                other.execute("UPDATE learning_records SET review_note = 'concurrent' WHERE id = 'record'")
                blocked.append(False)
            except sqlite3.OperationalError as error:
                blocked.append("locked" in str(error).lower())
            finally:
                other.close()

        conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(review_server, "connect_database", guarded_connect)
    payload = {"projectId": "project-lock", "skill": "code-review"}
    if operation == "overlay":
        review_server.delete_overlay({**payload, "overlayId": "overlay"})
    elif operation == "summary":
        review_server.delete_summary({**payload, "version": 1})
    else:
        review_server.update_record({**payload, "recordId": "record", "action": "EXCLUDED"})
    assert blocked == [True]


def test_single_database_page_fetches_only_requested_rows(tmp_path, monkeypatch):
    database = tmp_path / "page.sqlite"
    connection = connect_database(database)
    with connection:
        connection.executemany(
            "INSERT INTO learning_records (id, project_id, project_name, project_path, skill, captured_at, output_json) "
            "VALUES (?, 'project-page', 'project', ?, 'code-review', ?, '{}')",
            [(f"record-{index:03}", str(tmp_path), f"2026-09-17T00:{index:02}:00Z") for index in range(60)],
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": "project-page", "name": "project", "path": str(tmp_path), "database": str(database),
    }])
    original_connect = sqlite3.connect
    queries = []

    def traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(queries.append)
        return conn

    monkeypatch.setattr(review_server.sqlite3, "connect", traced_connect)
    page = review_server.query_record_page({"page": ["3"]})
    assert page["total"] == 60
    assert len(page["items"]) == 20
    assert page["items"][0]["id"] == "record-019"
    assert any("LIMIT 20 OFFSET 40" in query for query in queries)


def test_shared_record_page_keeps_detail_queries_bounded(tmp_path, monkeypatch):
    project_id = "project-shared-page"
    project = tmp_path / "project"
    project.mkdir()
    databases = {}
    shared_id = "shared-page"
    for skill in ("code-review", "plan"):
        database = tmp_path / f"{skill}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.executemany(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at,
                    output_json, shared_capture_id, shared_capture_complete, capture_source)
                   VALUES (?, ?, 'project', ?, ?, ?, '{}', ?, ?, ?)""",
                [
                    (
                        f"record-{skill}-{index:03}", project_id, str(project), skill,
                        f"2026-09-17T00:{index:02}:00Z",
                        shared_id if index == 29 else None,
                        1 if index == 29 else 0,
                        "HOST_HOOK" if index == 29 else "SKILL_CONTRACT",
                    )
                    for index in range(30)
                ],
            )
        connection.close()
        databases[skill] = str(database)
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases,
        "status": "ACTIVE",
    }])
    original_connect = sqlite3.connect
    queries = []

    def traced_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(review_server.sqlite3, "connect", traced_connect)

    page = review_server.query_record_page({"page": ["1"], "project": [project_id]})

    detail_queries = [
        query for query in queries
        if query.lstrip().upper().startswith("SELECT * FROM LEARNING_RECORDS")
    ]
    assert page["total"] == 59
    assert len(page["items"]) == 20
    assert len(detail_queries) == 2
    assert all("LIMIT 20 OFFSET 0" in query for query in detail_queries)


def test_record_page_uses_stable_ties_and_one_database_read_snapshot(tmp_path, monkeypatch):
    database = tmp_path / "page.sqlite"
    connection = connect_database(database)
    with connection:
        connection.executemany(
            "INSERT INTO learning_records (id, project_id, project_name, project_path, skill, captured_at, output_json) "
            "VALUES (?, 'project-page', 'project', ?, 'code-review', '2026-09-17T00:00:00Z', '{}')",
            [(f"record-{index:03}", str(tmp_path)) for index in range(25)],
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": "project-page", "name": "project", "path": str(tmp_path), "database": str(database),
    }])
    original_connect = sqlite3.connect
    blocked_writes = []

    def traced_connect(*args, **kwargs):
        reader = original_connect(*args, **kwargs)

        def trace(statement):
            if not statement.startswith("SELECT * FROM learning_records"):
                return
            writer = original_connect(database, timeout=0)
            try:
                writer.execute("INSERT INTO learning_records "
                               "(id, project_id, project_name, project_path, skill, captured_at) "
                               "VALUES ('new-record', 'project-page', 'project', ?, 'code-review', '2026-09-18T00:00:00Z')",
                               (str(tmp_path),))
                writer.commit()
                blocked_writes.append(False)
            except sqlite3.OperationalError as error:
                blocked_writes.append("locked" in str(error).lower())
            finally:
                writer.close()

        reader.set_trace_callback(trace)
        return reader

    monkeypatch.setattr(review_server.sqlite3, "connect", traced_connect)
    first = review_server.query_record_page({"page": ["1"]})
    second = review_server.query_record_page({"page": ["2"]})
    assert first["total"] == second["total"] == 25
    assert [item["id"] for item in first["items"]] == [f"record-{index:03}" for index in range(24, 4, -1)]
    assert [item["id"] for item in second["items"]] == [f"record-{index:03}" for index in range(4, -1, -1)]
    assert blocked_writes == [True, True]


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "skills" / "learning-collector" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import review_server
import overlay_evaluator
from forge_cli.learning_collector import connect_database
from refinement_quality import SKILL_CRITERIA, evidence_packet


def test_retry_summary_generation_preserves_original_job_parameters(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    call_llm = object()
    monkeypatch.setattr(
        review_server, "_summary_generation_scope",
        lambda project_id, skill: ({"projectId": project_id}, database, skill),
    )
    monkeypatch.setattr(
        review_server, "summary_job_status",
        lambda _database, *, job_id: {
            "jobId": job_id, "projectId": "project", "skill": "plan",
        },
    )
    monkeypatch.setattr(
        review_server, "_summary_llm",
        lambda: ({"model": "test-model", "baseUrl": "https://example.test/v1", "wireApi": "responses"}, call_llm),
    )
    monkeypatch.setattr(review_server, "_skill_text", lambda skill: f"# {skill}")
    captured = {}

    def retry(database_path, **kwargs):
        captured.update({"database": database_path, **kwargs})
        return {"jobId": "retry-job", "language": "en"}

    monkeypatch.setattr(review_server, "retry_summary_job", retry)

    result = review_server.retry_summary_generation({
        "projectId": "project", "skill": "plan", "jobId": "failed-job",
        "language": "fr",
    })

    assert result == {"jobId": "retry-job", "language": "en"}
    assert captured == {
        "database": database, "previous_job_id": "failed-job",
        "skill_text": "# plan", "model": "test-model",
        "call_llm": call_llm,
        "provider_identity": review_server._summary_provider_identity({
            "baseUrl": "https://example.test/v1", "wireApi": "responses",
        }),
    }


def test_summary_service_identity_tracks_endpoint_and_protocol_without_credentials():
    config = {"baseUrl": "https://example.test/v1/", "wireApi": "responses", "apiKey": "secret"}
    identity = review_server._summary_provider_identity(config)
    assert identity.startswith("sha256:")
    assert "secret" not in identity
    assert review_server._summary_provider_identity({**config, "apiKey": "changed"}) == identity
    assert review_server._summary_provider_identity({**config, "baseUrl": "https://example.test/v1"}) == identity
    assert review_server._summary_provider_identity({**config, "baseUrl": "https://other.test/v1"}) != identity
    assert review_server._summary_provider_identity({**config, "wireApi": "chat_completions"}) != identity


def test_review_server_does_not_recover_jobs_without_service_ownership(monkeypatch):
    events = []

    class Server:
        def serve_forever(self):
            events.append("serve")

        def server_close(self):
            events.append("close")

    @contextmanager
    def unavailable_lock(_path, *, timeout):
        assert timeout == 0
        raise TimeoutError("already owned")
        yield

    monkeypatch.setattr(review_server, "ThreadingHTTPServer", lambda address, handler: Server())
    monkeypatch.setattr(review_server, "_registry_file_lock", unavailable_lock)
    monkeypatch.setattr(
        review_server, "recover_summary_generation_jobs",
        lambda: events.append("recover"),
    )

    with pytest.raises(TimeoutError, match="already owned"):
        review_server.serve_review_server(9876, "token")

    assert events == ["close"]


def test_review_server_recovers_only_after_taking_service_ownership(monkeypatch):
    events = []

    class Server:
        def serve_forever(self):
            events.append("serve")

        def server_close(self):
            events.append("close")

    @contextmanager
    def owned_lock(path, *, timeout):
        assert path == review_server.SERVICE_OWNER_PATH
        assert timeout == 0
        events.append("lock")
        yield
        events.append("unlock")

    monkeypatch.setattr(review_server, "ThreadingHTTPServer", lambda address, handler: Server())
    monkeypatch.setattr(review_server, "_registry_file_lock", owned_lock)
    monkeypatch.setattr(
        review_server, "recover_summary_generation_jobs",
        lambda: events.append("recover"),
    )

    review_server.serve_review_server(9876, "fixed-token")

    assert review_server.SERVICE_TOKEN == "fixed-token"
    assert events == ["lock", "recover", "serve", "unlock", "close"]


def _insert_releasable_v6_summary(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    skill: str = "code-review",
    version: int = 1,
    summary_id: str | None = None,
    rules: list[dict] | None = None,
    source_ids: list[str] | None = None,
    final_rules: list[dict] | None = None,
) -> dict:
    summary_id = summary_id or f"summary-{version}"
    record_id = f"record-{version}"
    source_ids = source_ids or [record_id]
    job_id = f"job-{version}"
    rules = rules or [{
        "id": f"rule-{version}",
        "stage": "FINAL_VALIDATION",
        "status": "CONFIRMED",
        "trigger": "Before returning the final review",
        "instruction": "Check that every finding has direct evidence.",
        "verification": "Verify each finding cites an exact file and line.",
        "sourceRecordIds": [record_id],
    }]
    rules = [dict(rule) for rule in rules]
    for rule in rules:
        rule.setdefault("supportCount", len(rule.get("sourceRecordIds", [])))
        rule.setdefault("sourceIdsTruncated", False)
    final_rules = [dict(rule, status="PENDING") for rule in (final_rules or rules)]
    snapshot = {
        "format": "forge-skill-training-summary-v6",
        "projectId": project_id,
        "skill": skill,
        "version": version,
        "status": "REVIEWED",
        "sourceCount": len(source_ids),
        "generation": {
            "mode": "llm-direct",
            "model": "summary-model",
            "promptVersion": "llm-summary-map-reduce-v1",
            "sourceDigest": f"sha256:source-{version}",
            "skillDigest": "sha256:skill",
            "outputLanguage": "zh-CN",
        },
        "coverage": {
            "sourceRecords": len(source_ids),
            "processedRecords": len(source_ids),
            "coverageRate": 1.0,
        },
        "quality": {
            "humanReviewRequired": True,
            "allInputsDispositioned": True,
        },
        "rules": rules,
    }
    connection.executemany(
        "INSERT INTO learning_records "
        "(id, project_id, project_name, project_path, skill, captured_at, output_json, reviewed) "
        "VALUES (?, ?, 'project', '.', ?, '2026-09-14T00:00:00Z', ?, 1)",
        ((source_id, project_id, skill, json.dumps({"source": source_id})) for source_id in source_ids),
    )
    connection.execute(
        "INSERT INTO learning_summaries "
        "(id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
        "VALUES (?, ?, ?, ?, '2026-09-14T00:00:00Z', ?, ?, 'REVIEWED')",
        (summary_id, project_id, skill, version, len(source_ids), json.dumps(snapshot, ensure_ascii=False)),
    )
    connection.executemany(
        "INSERT INTO learning_summary_sources (summary_id, record_id) VALUES (?, ?)",
        ((summary_id, source_id) for source_id in source_ids),
    )
    for rule in final_rules:
        connection.executemany(
            "INSERT INTO learning_summary_rule_sources (summary_id, rule_id, record_id) VALUES (?, ?, ?)",
            ((summary_id, rule["id"], source_id) for source_id in rule["sourceRecordIds"]),
        )
    connection.execute(
        """INSERT INTO summary_generation_jobs
           (id, project_id, skill, status, window_months, cutoff_at, source_digest,
            skill_digest, model, prompt_version, language, source_count, total_batches,
            completed_batches, summary_id, created_at, started_at, completed_at)
           VALUES (?, ?, ?, 'SUCCEEDED', 6, '2026-03-14T00:00:00Z', ?, ?, ?, ?, ?, ?,
                   1, 1, ?, '2026-09-14T00:00:00Z', '2026-09-14T00:00:00Z',
                   '2026-09-14T00:01:00Z')""",
        (
            job_id, project_id, skill, snapshot["generation"]["sourceDigest"],
            snapshot["generation"]["skillDigest"], snapshot["generation"]["model"],
            snapshot["generation"]["promptVersion"], snapshot["generation"]["outputLanguage"],
            len(source_ids), summary_id,
        ),
    )
    connection.executemany(
        "INSERT INTO summary_generation_sources (job_id, record_id, ordinal, record_digest) "
        "VALUES (?, ?, ?, ?)",
        ((job_id, source_id, index, f"sha256:{source_id}") for index, source_id in enumerate(source_ids)),
    )
    connection.execute(
        """INSERT INTO summary_generation_batches
           (job_id, phase, level, batch_index, input_digest, status, item_count,
            result_json, usage_json, created_at, completed_at)
           VALUES (?, 'FINAL', 1, 0, ?, 'SUCCEEDED', ?, ?, '{}',
                   '2026-09-14T00:00:00Z', '2026-09-14T00:01:00Z')""",
        (
            job_id, f"sha256:final-{version}", len(final_rules),
            json.dumps({"decisions": [], "rules": final_rules}, ensure_ascii=False),
        ),
    )
    return snapshot


def _configure_overlay_project(monkeypatch, project_id: str, project: Path, database: Path) -> None:
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id,
        "name": "project",
        "path": str(project),
        "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})


def test_overlay_llm_evaluation_applies_user_approved_default_gate(tmp_path):
    calls = []

    def call_llm(instruction, payload):
        calls.append((instruction, payload))
        usage = {"status": "reported", "inputTokens": 10, "outputTokens": 5, "totalTokens": 15}
        if "blind A/B evaluator" not in instruction:
            return ("baseline answer" if len(calls) == 1 else "candidate answer"), usage
        return json.dumps({
            "A": {
                "hardRequirements": [True, True, True], "forbiddenBehaviorsObserved": [False, False],
                "qualityScore": 70, "hardErrors": [], "notes": "baseline",
            },
            "B": {
                "hardRequirements": [True, True, True], "forbiddenBehaviorsObserved": [False, False],
                "qualityScore": 80, "hardErrors": [], "notes": "candidate",
            },
            "preferred": "B",
            "newHardErrors": [],
            "obviousRegression": {"response": "none", "reason": "none"},
        }), usage

    report, artifact = overlay_evaluator.evaluate_overlay(
        forge_root=REPOSITORY_ROOT / "forge",
        skill_root=REPOSITORY_ROOT / "skills" / "learning-collector",
        skill="code-review", overlay_content="# Overlay\n- Check negative ports.\n",
        model="judge-model", output_root=tmp_path / "evaluations", call_llm=call_llm,
        baseline_overlay_content="# Active Overlay\n- Existing rule.\n",
    )

    assert report["passed"] is True
    assert report["caseCount"] == 3
    assert report["confidence"] == "MEDIUM"
    assert report["baseline"] == "active_overlay"
    assert "Existing rule" in calls[0][0]
    assert [gate["id"] for gate in report["gates"]] == [
        "minimum_case_coverage", "no_new_hard_errors", "candidate_average_not_lower",
        "key_checkpoint_rate_not_lower", "no_obvious_single_case_regression",
    ]
    assert report["usage"]["totalTokens"] == 135
    assert artifact["cases"][0]["responses"]["candidate"] == "candidate answer"
    assert not any((tmp_path / "evaluations" / ".fixtures").iterdir())


def test_overlay_evaluation_reuses_only_baseline_calls_and_can_force_refresh(tmp_path):
    def run(*, force=False):
        calls = []

        def call_llm(instruction, payload):
            calls.append(instruction)
            usage = {"status": "reported", "inputTokens": 1, "outputTokens": 1, "totalTokens": 2}
            if "blind A/B evaluator" not in instruction:
                return f"generated response {len(calls)}", usage
            hard_count = len(payload["hardRequirements"])
            forbidden_count = len(payload["forbiddenBehaviors"])
            score = {
                "hardRequirements": [True] * hard_count,
                "forbiddenBehaviorsObserved": [False] * forbidden_count,
                "qualityScore": 80, "hardErrors": [], "notes": "ok",
            }
            return json.dumps({
                "A": score, "B": score, "preferred": "tie", "newHardErrors": [],
                "obviousRegression": {"response": "none", "reason": "none"},
            }), usage

        report, _artifact = overlay_evaluator.evaluate_overlay(
            forge_root=REPOSITORY_ROOT / "forge",
            skill_root=REPOSITORY_ROOT / "skills" / "learning-collector",
            skill="code-review", overlay_content="candidate", model="judge-model",
            output_root=tmp_path / "evaluations", call_llm=call_llm,
            baseline_cache_identity="responses:example-endpoint",
            force_baseline=force,
        )
        return report, calls

    first, first_calls = run()
    second, second_calls = run()
    forced, forced_calls = run(force=True)

    assert len(first_calls) == first["caseCount"] * 3
    assert first["baselineCache"] == {
        "enabled": True, "forced": False, "hits": 0, "misses": first["caseCount"],
    }
    assert len(second_calls) == second["caseCount"] * 2
    assert second["baselineCache"]["hits"] == second["caseCount"]
    assert second["usage"]["cachedCalls"] == second["caseCount"]
    assert len(forced_calls) == forced["caseCount"] * 3
    assert forced["baselineCache"]["forced"] is True


def test_overlay_llm_evaluation_rejects_single_case_regression(tmp_path):
    responses = iter(("baseline", "candidate") * 3)

    def call_llm(instruction, _payload):
        usage = {"status": "unavailable", "reason": "backend_did_not_report_usage"}
        if "blind A/B evaluator" not in instruction:
            return next(responses), usage
        return json.dumps({
            "A": {
                "hardRequirements": [True, True, True], "forbiddenBehaviorsObserved": [False, False],
                "qualityScore": 90, "hardErrors": [], "notes": "baseline",
            },
            "B": {
                "hardRequirements": [False, True, True], "forbiddenBehaviorsObserved": [True, False],
                "qualityScore": 60, "hardErrors": ["missed concrete bug"], "notes": "candidate",
            },
            "preferred": "A",
            "newHardErrors": [{"response": "B", "description": "missed concrete bug"}],
            "obviousRegression": {"response": "B", "reason": "missed a supported finding"},
        }), usage

    report, _artifact = overlay_evaluator.evaluate_overlay(
        forge_root=REPOSITORY_ROOT / "forge",
        skill_root=REPOSITORY_ROOT / "skills" / "learning-collector",
        skill="code-review", overlay_content="# Overlay\n- Prefer brevity.\n",
        model="judge-model", output_root=tmp_path / "evaluations", call_llm=call_llm,
    )

    assert report["passed"] is False
    assert next(gate for gate in report["gates"] if gate["id"] == "minimum_case_coverage")["passed"] is True
    assert any(not gate["passed"] for gate in report["gates"])
    assert report["usage"]["cost"] == {"status": "cost_unavailable", "amount": None, "currency": None}


def test_overlay_llm_evaluation_fails_closed_without_http_compatible_case(tmp_path):
    with pytest.raises(ValueError, match="no HTTP-compatible fixed read-only evaluation cases"):
        overlay_evaluator.evaluate_overlay(
            forge_root=REPOSITORY_ROOT / "forge",
            skill_root=REPOSITORY_ROOT / "skills" / "learning-collector",
            skill="implement", overlay_content="# Overlay\n- Keep changes scoped.\n",
            model="judge-model", output_root=tmp_path / "evaluations",
            call_llm=lambda *_args: pytest.fail("LLM must not run without a compatible case"),
        )


def test_overlay_evaluation_readiness_uses_the_runtime_case_filter():
    forge_root = REPOSITORY_ROOT / "forge"

    ready = overlay_evaluator.evaluation_readiness(forge_root, "code-review")
    not_ready = overlay_evaluator.evaluation_readiness(forge_root, "implement")

    assert ready["ready"] is True
    assert ready["caseCount"] >= ready["requiredCaseCount"] == 3
    assert not_ready["ready"] is False
    assert not_ready["caseCount"] < not_ready["requiredCaseCount"]


def test_overlay_llm_evaluation_does_not_pass_with_fewer_than_three_cases(tmp_path):
    calls = []

    def call_llm(instruction, payload):
        calls.append((instruction, payload))
        usage = {"status": "unavailable", "reason": "backend_did_not_report_usage"}
        if "blind A/B evaluator" not in instruction:
            return "acceptable response", usage
        hard = [True] * len(payload["hardRequirements"])
        forbidden = [False] * len(payload["forbiddenBehaviors"])
        score = {
            "hardRequirements": hard, "forbiddenBehaviorsObserved": forbidden,
            "qualityScore": 80, "hardErrors": [], "notes": "acceptable",
        }
        return json.dumps({
            "A": score, "B": score, "preferred": "tie", "newHardErrors": [],
            "obviousRegression": {"response": "none", "reason": "none"},
        }), usage

    with pytest.raises(ValueError, match="requires at least 3 compatible fixed cases"):
        overlay_evaluator.evaluate_overlay(
            forge_root=REPOSITORY_ROOT / "forge",
            skill_root=REPOSITORY_ROOT / "skills" / "learning-collector",
            skill="architecture-design", overlay_content="# Overlay\n- Keep tradeoffs explicit.\n",
            model="judge-model", output_root=tmp_path / "evaluations", call_llm=call_llm,
        )

    assert calls == []


def finding(title: str, direction: str, severity: str = "High") -> dict:
    return {
        "title": title,
        "severity": severity,
        "suggested_direction": direction,
        "why_it_matters": "The current implementation can lose project registration data.",
        "confidence": "High",
    }
def test_overlay_schema_tracks_sources_and_allows_one_active_overlay(tmp_path):
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    try:
        connection.execute(
            "INSERT INTO skill_overlays "
            "(id, project_id, skill, version, content, manifest_json, content_digest, created_at) "
            "VALUES ('overlay-1', 'project-1', 'code-review', 1, '# v1', '{}', 'sha256:1', '2026-09-14T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO skill_overlay_sources(overlay_id, summary_id, summary_digest) "
            "VALUES ('overlay-1', 'summary-1', 'sha256:s1')"
        )
        connection.execute(
            "UPDATE skill_overlays SET status = 'ACTIVE' WHERE id = 'overlay-1'"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO skill_overlays "
                "(id, project_id, skill, version, content, manifest_json, content_digest, created_at, status) "
                "VALUES ('overlay-2', 'project-1', 'code-review', 2, '# v2', '{}', 'sha256:2', '2026-09-14T00:00:00Z', 'ACTIVE')"
            )
        assert connection.execute(
            "SELECT summary_id FROM skill_overlay_sources WHERE overlay_id = 'overlay-1'"
        ).fetchone()[0] == "summary-1"
    finally:
        connection.close()


def test_create_overlay_uses_one_reviewed_ai_summary_for_draft(tmp_path, monkeypatch):
    project_id = "project-overlay"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id, version=1)
        _insert_releasable_v6_summary(connection, project_id=project_id, version=2)
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project),
                     "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})

    with pytest.raises(ValueError, match="exactly one"):
        review_server.create_overlay({
            "projectId": project_id, "skill": "code-review", "summaryVersions": [1, 2],
        })
    created = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
        "language": "zh-CN",
    })

    assert created["status"] == "DRAFT"
    assert created["version"] == 1
    assert created["manifest"]["summaryVersions"] == [1]
    assert created["manifest"]["sourceSummary"]["id"] == "summary-1"
    assert created["manifest"]["sourceSummary"]["format"] == "forge-skill-training-summary-v6"
    assert created["manifest"]["executionSource"] == "content"
    assert created["manifest"]["outputLanguage"] == "zh-CN"
    assert "# 项目 Overlay：code-review" in created["content"]
    assert created["content"].count("Check that every finding has direct evidence") == 1
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT status FROM skill_overlays").fetchone()[0] == "DRAFT"
        assert check.execute("SELECT COUNT(*) FROM skill_overlay_sources").fetchone()[0] == 1
    with pytest.raises(ValueError, match="referenced by an Overlay"):
        review_server.review_summary({
            "projectId": project_id, "skill": "code-review", "version": 1, "rules": [],
        })
    with pytest.raises(ValueError, match="referenced by an Overlay"):
        review_server.delete_summary({
            "projectId": project_id, "skill": "code-review", "version": 1,
        })
    with pytest.raises(review_server.OverlayConflict) as conflict:
        review_server.create_overlay({
            "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
        })
    assert conflict.value.replaceable is True
    replaced = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
        "replaceExisting": True,
    })
    assert replaced["id"] == created["id"]
    assert replaced["version"] == created["version"]
    with pytest.raises(ValueError, match="read-only; copy it before editing"):
        review_server.review_overlay({
            "projectId": project_id, "skill": "skill.code_review", "overlayId": created["id"],
            "content": replaced["content"] + "\n- 人工补充校验。\n",
        })
    reviewed_overlay = review_server.review_overlay({
        "projectId": project_id, "skill": "skill.code_review", "overlayId": created["id"],
        "content": replaced["content"],
    })
    assert reviewed_overlay["status"] == "REVIEWED"
    with closing(sqlite3.connect(database)) as check, check:
        manifest = json.loads(check.execute("SELECT manifest_json FROM skill_overlays").fetchone()[0])
        assert manifest["executionSource"] == "content"
        assert manifest["origin"] == {"type": "SUMMARY_GENERATED"}
        assert "contentEdited" not in manifest
    def unavailable_llm():
        raise ValueError("LLM disabled for test")
    monkeypatch.setattr(review_server, "_configured_llm", unavailable_llm)
    rejected = review_server.evaluate_and_publish_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })
    assert rejected["status"] == "REJECTED"
    assert rejected["evaluation"]["behavior"]["error"] == "LLM disabled for test"
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT published_at FROM skill_overlays").fetchone()[0] is None
    monkeypatch.setattr(review_server, "_configured_llm", lambda: ({
        "model": "judge-model", "wireApi": "responses", "timeoutSeconds": 30,
        "endpoint": "https://example.test/v1/responses",
    }, "key"))
    monkeypatch.setattr(review_server, "evaluate_overlay", lambda **_kwargs: (
        {
            "format": "forge-overlay-behavior-evaluation-v1", "passed": True,
            "caseCount": 3, "confidence": "MEDIUM", "gates": [],
            "candidateOverlayDigest": reviewed_overlay["contentDigest"],
            "skillDigest": "sha256:" + hashlib.sha256(
                (REPOSITORY_ROOT / "skills" / "code-review" / "SKILL.md").read_bytes()
            ).hexdigest(),
            "corpusDigest": "sha256:" + hashlib.sha256(
                (REPOSITORY_ROOT / "forge" / "evals" / "skill-behavior-cases.json").read_bytes()
            ).hexdigest(),
        },
        {"format": "forge-overlay-behavior-evaluation-v1", "passed": True, "cases": []},
    ))
    published = review_server.evaluate_and_publish_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })
    assert published["status"] == "PUBLISHED"
    assert published["evaluation"]["passed"] is True
    assert published["evaluation"]["behavior"]["caseCount"] == 3
    with closing(sqlite3.connect(database)) as check, check:
        evaluation, published_at = check.execute(
            "SELECT evaluation_json, published_at FROM skill_overlays"
        ).fetchone()
        assert json.loads(evaluation)["passed"] is True
        assert published_at
    with pytest.raises(ValueError, match="already published"):
        review_server.evaluate_and_publish_overlay({
            "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
        })
    with closing(sqlite3.connect(database)) as check, check:
        original_evaluation = check.execute(
            "SELECT evaluation_json FROM skill_overlays WHERE id = ?", (created["id"],),
        ).fetchone()[0]
        stale = json.loads(original_evaluation)
        stale["behavior"]["skillDigest"] = "sha256:old-skill"
        check.execute(
            "UPDATE skill_overlays SET evaluation_json = ? WHERE id = ?",
            (json.dumps(stale), created["id"]),
        )
    with pytest.raises(ValueError, match="copy this Overlay to a new version and review/evaluate it"):
        review_server.activate_overlay({
            "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
        })
    recovered = review_server.copy_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })
    review_server.review_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": recovered["id"],
        "content": replaced["content"],
    })
    assert review_server.evaluate_and_publish_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": recovered["id"],
    })["status"] == "PUBLISHED"
    with closing(sqlite3.connect(database)) as check, check:
        check.execute("DELETE FROM skill_overlay_sources WHERE overlay_id = ?", (recovered["id"],))
        check.execute("DELETE FROM skill_overlays WHERE id = ?", (recovered["id"],))
        check.execute(
            "UPDATE skill_overlays SET evaluation_json = ? WHERE id = ?",
            (original_evaluation, created["id"]),
        )
    with closing(sqlite3.connect(database)) as check, check:
        check.execute(
            "INSERT INTO skill_overlays "
            "(id, project_id, skill, version, status, content, manifest_json, content_digest, created_at) "
            "VALUES ('overlay-new-baseline', ?, 'code-review', 2, 'ACTIVE', 'other', '{}', "
            "'sha256:other', '2026-09-14T01:00:00Z')",
            (project_id,),
        )
    activated = review_server.activate_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })
    assert activated["status"] == "ACTIVE"
    with closing(sqlite3.connect(database)) as check, check:
        check.execute("DELETE FROM skill_overlays WHERE id = 'overlay-new-baseline'")
    assert review_server.disable_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })["status"] == "DISABLED"


def test_copied_overlay_is_editable_and_does_not_replace_generated_draft(tmp_path, monkeypatch):
    project_id = "project-overlay-copy"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id)
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)
    generated = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
    })

    copied = review_server.copy_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": generated["id"],
    })

    assert copied["version"] == 2
    assert copied["origin"] == "MANUAL_COPY"
    edited_content = generated["content"] + "\n- Manually verify the project-specific boundary.\n"
    reviewed = review_server.review_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": copied["id"],
        "content": edited_content,
    })
    assert reviewed["status"] == "REVIEWED"
    connection = connect_database(database)
    connection.row_factory = sqlite3.Row
    copied_row = connection.execute(
        "SELECT * FROM skill_overlays WHERE id = ?", (copied["id"],)
    ).fetchone()
    manifest = json.loads(copied_row["manifest_json"])
    structural = review_server._structural_overlay_evaluation(
        connection, copied_row, "code-review",
    )
    connection.close()
    assert manifest["origin"]["type"] == "MANUAL_COPY"
    assert manifest["origin"]["sourceOverlay"] == {
        "id": generated["id"],
        "version": 1,
        "contentDigest": "sha256:" + hashlib.sha256(generated["content"].encode()).hexdigest(),
    }
    assert manifest["contentEdited"] is True
    assert structural["passed"] is True

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("DELETE FROM skill_overlays WHERE id = ?", (generated["id"],))
    regenerated = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
    })
    assert regenerated["version"] == 3
    assert regenerated["manifest"]["origin"] == {"type": "SUMMARY_GENERATED"}


def test_overlay_content_follows_selected_language_and_rejects_unknown_language():
    rules = [
        {"stage": "PRE_CHECK", "instruction": "检查输入边界。"},
        {"stage": "FINAL_VALIDATION", "instruction": "确认输出完整。"},
    ]

    chinese = review_server._overlay_content("code-review", rules, "zh-CN")
    english = review_server._overlay_content("code-review", rules, "en")

    assert "# 项目 Overlay：code-review" in chinese
    assert "## 执行前附加检查" in chinese
    assert "## 输出前附加校验" in chinese
    assert "# Project Overlay: code-review" in english
    assert "## Additional Pre-Review Checks" in english
    assert "检查输入边界。" in chinese
    assert "检查输入边界。" in english
    with pytest.raises(ValueError, match="language must be zh-CN or en"):
        review_server.create_overlay({
            "projectId": "project", "skill": "code-review",
            "summaryVersions": [1], "language": "fr",
        })


def test_create_overlay_rejects_unreviewed_summary(tmp_path, monkeypatch):
    project_id = "project-overlay-draft"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    connection.execute(
        "INSERT INTO learning_summaries "
        "(id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
        "VALUES ('summary-draft', ?, 'code-review', 1, '2026-09-14T00:00:00Z', 1, ?, 'DRAFT')",
        (project_id, json.dumps({"format": "forge-skill-training-summary-v5", "status": "DRAFT", "rules": []})),
    )
    connection.commit()
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project),
                     "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    with pytest.raises(ValueError, match="must be REVIEWED"):
        review_server.create_overlay({"projectId": project_id, "skill": "code-review", "summaryVersions": [1]})


def test_create_overlay_rejects_reviewed_summary_without_confirmed_rules(tmp_path, monkeypatch):
    project_id = "project-no-confirmed-rules"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    rules = [{
        "id": "rule-excluded", "stage": "FINAL_VALIDATION", "status": "EXCLUDED",
        "trigger": "Before returning the final review",
        "instruction": "Check direct evidence.",
        "verification": "Verify every finding.",
        "sourceRecordIds": ["record-1"],
    }]
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id, rules=rules)
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)

    with pytest.raises(ValueError, match="no confirmed rules"):
        review_server.create_overlay({
            "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
        })


@pytest.mark.parametrize(
    ("corruption", "message"),
    [
        ("v5", "not a reviewed AI Summary v6"),
        ("missing_job", "no unique successful generation job"),
        ("mismatched_job_sources", "generation lineage does not match its job"),
        ("wrong_job_scope", "generation lineage does not match its job"),
        ("missing_rule_source", "incomplete rule lineage"),
        ("added_rule_source", "incomplete rule lineage"),
        ("swapped_rule_source", "incomplete rule lineage"),
        ("missing_trigger", "incomplete executable rule metadata"),
        ("wrong_source_count", "AI Summary quality gate"),
    ],
)
def test_create_overlay_rejects_summary_without_complete_v6_lineage(
    tmp_path, monkeypatch, corruption, message,
):
    project_id = "project-invalid-v6"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    with connection:
        snapshot = _insert_releasable_v6_summary(connection, project_id=project_id)
        if corruption == "v5":
            snapshot["format"] = "forge-skill-training-summary-v5"
        elif corruption == "missing_job":
            connection.execute("DELETE FROM summary_generation_jobs WHERE id = 'job-1'")
        elif corruption == "mismatched_job_sources":
            connection.execute("DELETE FROM summary_generation_sources WHERE job_id = 'job-1'")
        elif corruption == "wrong_job_scope":
            connection.execute(
                "UPDATE summary_generation_jobs SET project_id = 'project-other' WHERE id = 'job-1'"
            )
        elif corruption in {"added_rule_source", "swapped_rule_source"}:
            connection.execute(
                "INSERT INTO learning_records "
                "(id, project_id, project_name, project_path, skill, captured_at, output_json, reviewed) "
                "VALUES ('record-outsider', ?, 'project', '.', 'code-review', "
                "'2026-09-14T00:00:00Z', '{}', 1)",
                (project_id,),
            )
            if corruption == "swapped_rule_source":
                connection.execute(
                    "DELETE FROM learning_summary_rule_sources "
                    "WHERE summary_id = 'summary-1' AND rule_id = 'rule-1' AND record_id = 'record-1'"
                )
            connection.execute(
                "INSERT INTO learning_summary_rule_sources(summary_id, rule_id, record_id) "
                "VALUES ('summary-1', 'rule-1', 'record-outsider')"
            )
        elif corruption == "missing_rule_source":
            connection.execute(
                "DELETE FROM learning_summary_rule_sources "
                "WHERE summary_id = 'summary-1' AND rule_id = 'rule-1'"
            )
        elif corruption == "missing_trigger":
            snapshot["rules"][0]["trigger"] = ""
        elif corruption == "wrong_source_count":
            connection.execute(
                "UPDATE learning_summaries SET source_count = 2 WHERE id = 'summary-1'"
            )
        if corruption in {"v5", "missing_trigger"}:
            connection.execute(
                "UPDATE learning_summaries SET summary_json = ? WHERE id = 'summary-1'",
                (json.dumps(snapshot),),
            )
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)

    with pytest.raises(ValueError, match=message):
        review_server.create_overlay({
            "projectId": project_id,
            "skill": "code-review",
            "summaryVersions": [1],
        })


def test_create_overlay_rejects_duplicate_confirmed_rules(tmp_path, monkeypatch):
    project_id = "project-duplicate-rules"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    rules = [{
        "id": f"rule-{index}",
        "stage": "FINAL_VALIDATION",
        "status": "CONFIRMED",
        "trigger": "Before returning the final review",
        "instruction": "Check that every finding has direct evidence.",
        "verification": "Verify each finding cites an exact file and line.",
        "sourceRecordIds": ["record-1"],
    } for index in (1, 2)]
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id, rules=rules)
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)

    with pytest.raises(ValueError, match="duplicate confirmed rules"):
        review_server.create_overlay({
            "projectId": project_id,
            "skill": "code-review",
            "summaryVersions": [1],
        })


@pytest.mark.parametrize(
    ("corruption", "failed_check"),
    [
        ("second_source", "single_summary_source"),
        ("summary_digest", "source_summary"),
        ("manifest_identity", "manifest_summary"),
        ("rule_lineage", "rule_lineage"),
        ("generated_content", "deterministic_content"),
    ],
)
def test_structural_overlay_gate_rejects_source_lineage_tampering(
    tmp_path, monkeypatch, corruption, failed_check,
):
    project_id = "project-overlay-tamper"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id, version=1)
        _insert_releasable_v6_summary(connection, project_id=project_id, version=2)
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)
    created = review_server.create_overlay({
        "projectId": project_id,
        "skill": "code-review",
        "summaryVersions": [1],
    })

    connection = connect_database(database)
    connection.row_factory = sqlite3.Row
    with connection:
        if corruption == "second_source":
            summary_json = connection.execute(
                "SELECT summary_json FROM learning_summaries WHERE id = 'summary-2'"
            ).fetchone()[0]
            summary_digest = "sha256:" + hashlib.sha256(summary_json.encode()).hexdigest()
            connection.execute(
                "INSERT INTO skill_overlay_sources (overlay_id, summary_id, summary_digest) "
                "VALUES (?, 'summary-2', ?)",
                (created["id"], summary_digest),
            )
        elif corruption == "summary_digest":
            snapshot = json.loads(connection.execute(
                "SELECT summary_json FROM learning_summaries WHERE id = 'summary-1'"
            ).fetchone()[0])
            snapshot["reviewNote"] = "changed after Overlay creation"
            connection.execute(
                "UPDATE learning_summaries SET summary_json = ? WHERE id = 'summary-1'",
                (json.dumps(snapshot),),
            )
        elif corruption in {"manifest_identity", "rule_lineage"}:
            manifest = json.loads(connection.execute(
                "SELECT manifest_json FROM skill_overlays WHERE id = ?", (created["id"],)
            ).fetchone()[0])
            if corruption == "manifest_identity":
                manifest["sourceSummary"]["id"] = "summary-2"
            else:
                manifest["rules"][0]["sourceRuleId"] = "rule-missing"
            connection.execute(
                "UPDATE skill_overlays SET manifest_json = ? WHERE id = ?",
                (json.dumps(manifest), created["id"]),
            )
        else:
            changed_content = created["content"] + "\n- Unsupported manual change.\n"
            changed_digest = "sha256:" + hashlib.sha256(changed_content.encode()).hexdigest()
            connection.execute(
                "UPDATE skill_overlays SET content = ?, content_digest = ? WHERE id = ?",
                (changed_content, changed_digest, created["id"]),
            )
        row = connection.execute(
            "SELECT * FROM skill_overlays WHERE id = ?", (created["id"],)
        ).fetchone()
        evaluation = review_server._structural_overlay_evaluation(
            connection, row, "code-review",
        )
    connection.close()

    assert evaluation["passed"] is False
    checks = {item["id"]: item["passed"] for item in evaluation["checks"]}
    assert checks[failed_check] is False


def test_structural_evaluation_failure_is_persisted_as_rejected(tmp_path, monkeypatch):
    project_id = "project-structural-rejection"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "structural.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id)
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    created = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1],
    })
    review_server.review_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
        "content": created["content"],
    })
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("UPDATE learning_summaries SET lifecycle_status = 'DRAFT' WHERE id = 'summary-1'")
    monkeypatch.setattr(
        review_server, "_configured_llm",
        lambda: pytest.fail("LLM must not run when structural evaluation fails"),
    )

    result = review_server.evaluate_and_publish_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": created["id"],
    })

    assert result["status"] == "REJECTED"
    assert result["evaluation"]["structural"]["passed"] is False
    with closing(sqlite3.connect(database)) as connection, connection:
        stored = json.loads(connection.execute(
            "SELECT evaluation_json FROM skill_overlays WHERE id = ?", (created["id"],)
        ).fetchone()[0])
    assert stored["passed"] is False
    assert stored["behavior"] is None


def test_unpublished_overlay_cannot_be_activated(tmp_path, monkeypatch):
    project_id = "project-unpublished"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "unpublished.sqlite"
    connection = connect_database(database)
    connection.execute(
        """INSERT INTO skill_overlays
           (id, project_id, skill, version, status, content, manifest_json, content_digest, created_at)
           VALUES ('overlay-unpublished', ?, 'code-review', 1, 'REVIEWED', 'content', '{}',
                   'sha256:invalid', '2026-09-14T00:00:00Z')""",
        (project_id,),
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    with pytest.raises(ValueError, match="published before activation"):
        review_server.activate_overlay({
            "projectId": project_id, "skill": "code-review", "overlayId": "overlay-unpublished",
        })


def test_activation_rejects_skill_disabled_after_overlay_publication(tmp_path, monkeypatch):
    project_id = "project-disabled-overlay"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "disabled-overlay.sqlite"
    connection = connect_database(database)
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: set())

    with pytest.raises(ValueError, match="not enabled for learning"):
        review_server.activate_overlay({
            "projectId": project_id, "skill": "code-review", "overlayId": "overlay-any",
        })


def test_summary_source_record_cannot_be_changed_or_deleted(tmp_path, monkeypatch):
    project_id = "project-summary-source-lock"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "source-lock.sqlite"
    connection = connect_database(database)
    with connection:
        for record_id in ("record-locked", "record-free"):
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at, output_json)
                   VALUES (?, ?, 'project', ?, 'code-review', '2026-09-14T00:00:00Z', '{}')""",
                (record_id, project_id, str(project)),
            )
        connection.execute(
            """INSERT INTO learning_summaries
               (id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status)
               VALUES ('summary-lock', ?, 'code-review', 1, '2026-09-14T00:01:00Z', 1, '{}', 'DRAFT')""",
            (project_id,),
        )
        connection.execute(
            "INSERT INTO learning_summary_sources(summary_id, record_id) VALUES ('summary-lock', 'record-locked')"
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])

    for action in ("ACTIVE", "EXCLUDED", "DELETED"):
        with pytest.raises(ValueError, match="referenced by a Summary"):
            review_server.update_record({
                "projectId": project_id, "recordId": "record-locked", "action": action,
            })
    assert review_server.update_record({
        "projectId": project_id, "recordId": "record-free", "action": "DELETED",
    }) == {"updated": True, "disabledOverlay": None}


def test_delete_ai_summary_removes_generation_provenance(tmp_path, monkeypatch):
    project_id = "project-delete-ai-summary"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "summary.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id=project_id)
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)

    result = review_server.delete_summary({
        "projectId": project_id, "skill": "code-review", "version": 1,
    })

    assert result["deleted"] is True
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_sources").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_batches").fetchone()[0] == 0
    connection.close()


def test_overlay_auto_disables_after_more_than_ten_reviews_and_over_thirty_percent_negative(tmp_path, monkeypatch):
    project_id = "project-rollback"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "rollback.sqlite"
    connection = connect_database(database)
    digest = "sha256:" + "a" * 64
    evaluation = json.dumps({"passed": True})
    connection.execute(
        """INSERT INTO skill_overlays
           (id, project_id, skill, version, status, content, manifest_json, content_digest,
            created_at, evaluation_json, published_at, enabled_at)
           VALUES ('overlay-active', ?, 'code-review', 2, 'ACTIVE', 'content', '{}', ?,
                   '2026-09-14T00:00:00Z', ?, '2026-09-14T00:01:00Z', '2026-09-14T00:02:00Z')""",
        (project_id, digest, evaluation),
    )
    metadata = json.dumps({"appliedOverlay": {
        "id": "overlay-active", "projectId": project_id, "skill": "code-review",
        "version": 2, "contentDigest": digest,
    }})
    for index in range(12):
        connection.execute(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, captured_at,
                output_json, metadata_json)
               VALUES (?, ?, 'project', ?, 'code-review', ?, '{}', ?)""",
            (f"record-{index}", project_id, str(project), f"2026-09-14T00:{index:02d}:00Z", metadata),
        )
    connection.commit()
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])

    for index in range(10):
        action = "EXCLUDED" if index < 3 else "ACTIVE"
        assert review_server.update_record({
            "projectId": project_id, "recordId": f"record-{index}", "action": action,
        })
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT status FROM skill_overlays").fetchone()[0] == "ACTIVE"

    assert review_server.update_record({"projectId": project_id, "recordId": "record-10", "action": "DELETED"})
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT status FROM skill_overlays").fetchone()[0] == "ACTIVE"
        assert check.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 11

    result = review_server.update_record({
        "projectId": project_id, "recordId": "record-11", "action": "EXCLUDED",
    })
    disabled = result["disabledOverlay"]
    assert disabled["overlayId"] == "overlay-active"
    assert disabled["version"] == 2
    assert disabled["reviewedCount"] == 11
    assert disabled["negativeCount"] == 4
    assert disabled["negativeRate"] == 4 / 11
    assert disabled["disabledAt"]
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT status FROM skill_overlays").fetchone()[0] == "DISABLED"
        assert not any(row[0] in {"overlay_review_feedback", "overlay_auto_disable_events"}
                       for row in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))
def test_review_queries_and_updates_across_skill_databases(tmp_path, monkeypatch):
    project_id = "project-multi-skill"
    project = tmp_path / "project"
    project.mkdir()
    databases = {}
    for index, skill in enumerate(("code-review", "debug"), start=1):
        database = tmp_path / "forge-data" / "projects" / project_id / "learning" / skill / "learning.sqlite"
        database.parent.mkdir(parents=True)
        connection = connect_database(database)
        connection.execute(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, captured_at, output_json)
               VALUES (?, ?, 'project', ?, ?, ?, ?)""",
            (
                f"record-{skill}", project_id, str(project), skill,
                f"2026-09-0{index}T00:00:00Z", json.dumps({"result": skill}),
            ),
        )
        connection.execute(
            """INSERT INTO learning_summaries
               (id, project_id, skill, version, created_at, source_count, summary_json)
               VALUES (?, ?, ?, 1, ?, 1, '{}')""",
            (f"summary-{skill}", project_id, skill, f"2026-09-0{index}T01:00:00Z"),
        )
        connection.commit()
        connection.close()
        databases[skill] = str(database)
    registry_item = {
        "projectId": project_id,
        "name": "project",
        "path": str(project),
        "database": databases["code-review"],
        "databases": databases,
        "status": "ACTIVE",
    }
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])

    records = review_server.query_records({"project": [project_id]})
    summaries = review_server.query_summaries({"project": [project_id]})
    debug_records = review_server.query_records({"project": [project_id], "skill": ["debug"]})

    assert {record["skill"] for record in records} == {"code-review", "debug"}
    assert {summary["skill"] for summary in summaries} == {"code-review", "debug"}
    assert [record["id"] for record in debug_records] == ["record-debug"]
    assert review_server.update_record({
        "projectId": project_id, "recordId": "record-debug", "action": "DELETED",
    }) == {"updated": True, "disabledOverlay": None}
    with closing(sqlite3.connect(databases["code-review"])) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 1
    with closing(sqlite3.connect(databases["debug"])) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 0


def test_shared_hook_turn_is_listed_once_and_reviewed_across_skills(tmp_path, monkeypatch):
    project_id = "project-shared-review"
    project = tmp_path / "project"
    project.mkdir()
    databases = {}
    shared_id = "shared-review-once"
    for skill in ("code-review", "plan"):
        database = tmp_path / "forge-data" / "projects" / project_id / "learning" / skill / "learning.sqlite"
        database.parent.mkdir(parents=True)
        connection = connect_database(database)
        metadata = {"hookCapture": {
            "attribution": "SHARED_HOST_TURN",
            "sharedCaptureId": shared_id,
            "matchedInvocationCount": 2,
            "matchedSkills": ["code-review", "plan"],
        }}
        connection.execute(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, captured_at, output_json,
                metadata_json, shared_capture_id, shared_capture_complete,
                capture_source, hook_status)
               VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, ?, 1,
                       'HOST_HOOK', 'CAPTURED')""",
            (
                f"record-{skill}", project_id, str(project), skill,
                json.dumps({"finalResponse": "one shared response"}), json.dumps(metadata),
                shared_id,
            ),
        )
        connection.commit()
        connection.close()
        databases[skill] = str(database)
    registry_item = {
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases, "status": "ACTIVE",
    }
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])

    page = review_server.query_record_page({"page": ["1"], "project": [project_id]})

    assert page["total"] == 1
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert item["shared_capture_id"] == shared_id
    assert item["shared_record_count"] == 2
    assert item["shared_skills"] == ["code-review", "plan"]

    result = review_server.update_record({
        "projectId": project_id,
        "recordId": item["id"],
        "action": "ACTIVE",
        "editedContent": "reviewed shared evidence",
        "note": "reviewed once",
    })

    assert result["updatedCount"] == 2
    assert result["sharedCaptureId"] == shared_id
    assert result["sharedSkills"] == ["code-review", "plan"]
    for database in databases.values():
        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                "SELECT reviewed, review_status, edited_content, review_note FROM learning_records"
            ).fetchone()
        assert row == (1, "ACTIVE", "reviewed shared evidence", "reviewed once")


def test_shared_hook_review_rejects_a_missing_declared_skill_database(tmp_path, monkeypatch):
    project_id = "project-shared-missing-database"
    project = tmp_path / "project"
    project.mkdir()
    shared_id = "shared-missing-database"
    databases = {}
    metadata = {"hookCapture": {
        "attribution": "SHARED_HOST_TURN",
        "sharedCaptureId": shared_id,
        "matchedInvocationCount": 2,
        "matchedSkills": ["code-review", "plan"],
    }}
    for skill in ("code-review", "plan"):
        database = tmp_path / f"{skill}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at,
                    metadata_json, shared_capture_id, shared_capture_complete,
                    capture_source, hook_status)
                   VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, 1,
                           'HOST_HOOK', 'CAPTURED')""",
                (
                    f"record-{skill}", project_id, str(project), skill,
                    json.dumps(metadata), shared_id,
                ),
            )
        connection.close()
        databases[skill] = str(database)
    missing = Path(databases["plan"])
    missing.rename(missing.with_suffix(".missing"))
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases,
        "status": "ACTIVE",
    }])

    with pytest.raises(ValueError, match="database is unavailable for Skill: plan"):
        review_server.update_record({
            "projectId": project_id, "recordId": "record-code-review",
            "action": "EXCLUDED",
        })

    with closing(sqlite3.connect(databases["code-review"])) as connection:
        assert connection.execute(
            "SELECT reviewed, review_status FROM learning_records"
        ).fetchone() == (0, "ACTIVE")


def test_shared_hook_metadata_does_not_group_or_update_skill_contract_records(
    tmp_path, monkeypatch,
):
    project_id = "project-shared-fallback"
    project = tmp_path / "project"
    project.mkdir()
    shared_id = "shared-with-fallback"
    databases = {}
    for skill, source in (
        ("code-review", "SKILL_CONTRACT"),
        ("plan", "HOST_HOOK"),
        ("debug", "HOST_HOOK"),
    ):
        database = (
            tmp_path / "forge-data" / "projects" / project_id
            / "learning" / skill / "learning.sqlite"
        )
        database.parent.mkdir(parents=True)
        connection = connect_database(database)
        metadata = {"hookCapture": {
            "attribution": "SHARED_HOST_TURN",
            "sharedCaptureId": shared_id,
            "matchedInvocationCount": "invalid",
            "matchedSkills": ["code-review", "debug", "plan"],
        }}
        connection.execute(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, captured_at, output_json,
                metadata_json, shared_capture_id, shared_capture_complete,
                capture_source, hook_status)
               VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, ?, ?, ?,
                       'CAPTURED')""",
            (
                f"record-{skill}", project_id, str(project), skill,
                json.dumps({"result": skill}), json.dumps(metadata),
                shared_id,
                1 if source == "HOST_HOOK" else 0, source,
            ),
        )
        connection.commit()
        connection.close()
        databases[skill] = str(database)
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases,
        "status": "ACTIVE",
    }])

    page = review_server.query_record_page({"page": ["1"], "project": [project_id]})

    assert page["total"] == 2
    assert len(page["items"]) == 2
    contract = next(item for item in page["items"] if item["skill"] == "code-review")
    hook = next(item for item in page["items"] if item["capture_source"] == "HOST_HOOK")
    assert contract["shared_capture_id"] == shared_id
    assert contract.get("shared_review_group_id") is None
    assert "shared_skills" not in contract
    assert contract["shared_capture_pending"] is True
    assert hook["shared_capture_id"] == shared_id
    assert hook["shared_review_group_id"] == shared_id
    assert hook["shared_record_count"] == 2
    assert hook["shared_skills"] == ["debug", "plan"]

    with pytest.raises(ValueError, match="still finalizing"):
        review_server.update_record({
            "projectId": project_id,
            "recordId": contract["id"],
            "action": "ACTIVE",
        })

    result = review_server.update_record({
        "projectId": project_id, "recordId": hook["id"], "action": "EXCLUDED",
        "note": "auxiliary evidence only",
    })

    assert result["updatedCount"] == 2
    with closing(sqlite3.connect(databases["code-review"])) as connection:
        assert connection.execute(
            "SELECT reviewed, review_status FROM learning_records"
        ).fetchone() == (0, "ACTIVE")
    for skill in ("debug", "plan"):
        with closing(sqlite3.connect(databases[skill])) as connection:
            assert connection.execute(
                "SELECT reviewed, review_status FROM learning_records"
            ).fetchone() == (1, "EXCLUDED")


def test_shared_hook_review_rolls_back_all_databases_when_one_write_fails(
    tmp_path, monkeypatch,
):
    project_id = "project-shared-rollback"
    project = tmp_path / "project"
    project.mkdir()
    shared_id = "shared-rollback"
    databases = {}
    for skill in ("code-review", "plan"):
        database = tmp_path / f"{skill}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at,
                    metadata_json, shared_capture_id, shared_capture_complete,
                    capture_source, hook_status)
                   VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, 1,
                           'HOST_HOOK', 'CAPTURED')""",
                (
                    f"record-{skill}", project_id, str(project), skill,
                        json.dumps({"hookCapture": {
                            "attribution": "SHARED_HOST_TURN",
                            "sharedCaptureId": shared_id,
                            "matchedSkills": ["code-review", "plan"],
                        }}), shared_id,
                ),
            )
            if skill == "plan":
                connection.execute(
                    """CREATE TRIGGER reject_shared_review
                       BEFORE UPDATE ON learning_records
                       BEGIN SELECT RAISE(ABORT, 'forced shared review failure'); END"""
                )
        connection.close()
        databases[skill] = str(database)
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases,
        "status": "ACTIVE",
    }])

    with pytest.raises(sqlite3.IntegrityError, match="forced shared review failure"):
        review_server.update_record({
            "projectId": project_id, "recordId": "record-code-review",
            "action": "EXCLUDED", "note": "must be atomic",
        })

    for database in databases.values():
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute(
                "SELECT reviewed, review_status, review_note FROM learning_records"
            ).fetchone() == (0, "ACTIVE", "")


def test_shared_hook_review_waits_until_every_member_is_complete(tmp_path, monkeypatch):
    project_id = "project-shared-pending"
    project = tmp_path / "project"
    project.mkdir()
    shared_id = "shared-pending"
    databases = {}
    for skill, complete in (("code-review", 1), ("plan", 0)):
        database = tmp_path / f"{skill}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at,
                    metadata_json, shared_capture_id, shared_capture_complete,
                    capture_source, hook_status)
                   VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, ?,
                           'HOST_HOOK', 'CAPTURED')""",
                (
                    f"record-{skill}", project_id, str(project), skill,
                    json.dumps({"hookCapture": {
                        "attribution": "SHARED_HOST_TURN",
                        "sharedCaptureId": shared_id,
                        "matchedSkills": ["code-review", "plan"],
                    }}), shared_id, complete,
                ),
            )
        connection.close()
        databases[skill] = str(database)
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["code-review"], "databases": databases,
        "status": "ACTIVE",
    }])

    page = review_server.query_record_page({"page": ["1"], "project": [project_id]})
    assert page["items"][0]["shared_capture_pending"] is True

    with pytest.raises(ValueError, match="still finalizing"):
        review_server.update_record({
            "projectId": project_id, "recordId": page["items"][0]["id"],
            "action": "EXCLUDED",
        })

    for database in databases.values():
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute(
                "SELECT reviewed, review_status FROM learning_records"
            ).fetchone() == (0, "ACTIVE")


def test_shared_hook_review_rejects_more_than_eleven_skill_databases(
    tmp_path, monkeypatch,
):
    project_id = "project-shared-limit"
    project = tmp_path / "project"
    project.mkdir()
    shared_id = "shared-over-limit"
    databases = {}
    matched_skills = [f"skill-{index}" for index in range(12)]
    for index in range(12):
        skill = f"skill-{index}"
        database = tmp_path / f"{skill}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at,
                    metadata_json, shared_capture_id, shared_capture_complete,
                    capture_source, hook_status)
                   VALUES (?, ?, 'project', ?, ?, '2026-09-24T00:00:00Z', ?, ?, 1,
                           'HOST_HOOK', 'CAPTURED')""",
                (
                    f"record-{index}", project_id, str(project), skill,
                    json.dumps({"hookCapture": {
                        "attribution": "SHARED_HOST_TURN",
                        "sharedCaptureId": shared_id,
                        "matchedSkills": matched_skills,
                    }}), shared_id,
                ),
            )
        connection.close()
        databases[skill] = str(database)
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": databases["skill-0"], "databases": databases,
        "status": "ACTIVE",
    }])

    with pytest.raises(ValueError, match="at most 11 Skill databases"):
        review_server.update_record({
            "projectId": project_id, "recordId": "record-0", "action": "EXCLUDED",
        })

    for database in databases.values():
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute(
                "SELECT reviewed, review_status FROM learning_records"
            ).fetchone() == (0, "ACTIVE")


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        if self.offset >= len(self.payload):
            return b""
        if size is None or size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk
@pytest.mark.parametrize("reason", [None, "length", "content_filter", "tool_calls"])
def test_chat_rejects_unfinished_response(monkeypatch, reason):
    payload = {"choices": [{"finish_reason": reason, "message": {"content": "{}"}}]}
    monkeypatch.setattr(review_server.urllib.request, "urlopen",
                        lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(ValueError):
        review_server._call_llm({"endpoint": "https://example.test/v1/chat/completions",
                                "model": "test-model", "wireApi": "chat_completions", "timeoutSeconds": 60},
                               "test-key", "Return JSON", {})


class _FakeStreamingResponse:
    def __init__(self, payload: bytes):
        self.stream = io.BytesIO(payload)
        self.headers = {"Content-Type": "text/event-stream; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def readline(self, size=-1):
        return self.stream.readline(size)


@pytest.mark.parametrize("extra", [
    {"status": "incomplete"}, {"status": "failed"},
    {"status": "completed", "error": {"message": "failed"}},
])
def test_completed_stream_event_rejects_failed_response(extra):
    payload = {"type": "response.completed", "response": {"output_text": "{}", **extra}}
    stream = _FakeStreamingResponse(("data: " + json.dumps(payload) + "\n\n").encode())
    with pytest.raises(ValueError):
        review_server._read_responses_stream(stream, "test-key")


def test_chat_rejects_refusal_even_with_stop(monkeypatch):
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": "{}", "refusal": "Cannot comply"}}]}
    monkeypatch.setattr(review_server.urllib.request, "urlopen",
                        lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="did not finish successfully"):
        review_server._call_llm({"endpoint": "https://example.test/v1/chat/completions",
                                "model": "test-model", "wireApi": "chat_completions", "timeoutSeconds": 60},
                               "test-key", "Return JSON", {})
def test_review_summary_accepts_v6_and_preserves_ai_rule_metadata(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    snapshot = {
        "format": "forge-skill-training-summary-v6",
        "projectId": "project-v6", "skill": "code-review", "version": 1,
        "status": "DRAFT", "sourceCount": 1,
        "coverage": {"sourceRecords": 1, "processedRecords": 1, "finalRules": 1},
        "rules": [{
            "id": "rule-v6", "stage": "PRE_CHECK", "status": "PENDING",
            "title": "Validate evidence", "instruction": "Check direct evidence.",
            "trigger": "Before reporting a finding", "verification": "Cite an exact line.",
            "rationale": "Unsupported findings are unreliable.", "supportCount": 1,
            "sourceRecordIds": ["record-v6"],
        }],
    }
    with connection:
        connection.execute(
            "INSERT INTO learning_summaries "
            "(id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
            "VALUES ('summary-v6', 'project-v6', 'code-review', 1, 'now', 1, ?, 'DRAFT')",
            (json.dumps(snapshot),),
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": "project-v6", "database": str(database),
        "databases": {"code-review": str(database)},
    }])

    result = review_server.review_summary({
        "projectId": "project-v6", "skill": "code-review", "version": 1,
        "rules": [{
            "id": "rule-v6", "stage": "FINAL_VALIDATION", "status": "CONFIRMED",
            "instruction": "Verify every finding against direct evidence.",
        }],
    })

    assert result["status"] == "REVIEWED"
    assert result["statistics"] == {
        "pendingRules": 0, "confirmedRules": 1, "excludedRules": 0,
    }
    connection = connect_database(database)
    saved = json.loads(connection.execute(
        "SELECT summary_json FROM learning_summaries WHERE id = 'summary-v6'",
    ).fetchone()[0])
    connection.close()
    assert saved["rules"][0]["trigger"] == "Before reporting a finding"
    assert saved["rules"][0]["verification"] == "Cite an exact line."
    assert saved["review"]["confirmedRules"] == 1
    with pytest.raises(ValueError, match="reviewed Summary is read-only"):
        review_server.review_summary({
            "projectId": "project-v6", "skill": "code-review", "version": 1,
            "rules": [{"id": "rule-v6", "stage": "PRE_CHECK", "status": "EXCLUDED",
                       "instruction": "Unsaved change"}],
        })
    with closing(sqlite3.connect(database)) as check:
        stored, status = check.execute(
            "SELECT summary_json,lifecycle_status FROM learning_summaries WHERE id='summary-v6'",
        ).fetchone()
    assert json.loads(stored) == saved
    assert status == "REVIEWED"


def test_learning_pages_share_language_asset_and_ai_summary_contract():
    review_html = review_server.HTML_PATH.read_text(encoding="utf-8")
    versions_html = review_server.VERSIONS_PATH.read_text(encoding="utf-8")
    overlays_html = review_server.OVERLAYS_PATH.read_text(encoding="utf-8")
    i18n_javascript = review_server.I18N_PATH.read_text(encoding="utf-8")

    assert '/assets/learning-i18n.js' in review_html
    assert '/assets/learning-i18n.js' in versions_html
    assert '/assets/learning-i18n.js' in overlays_html
    assert 'forge-learning-language-v2' in i18n_javascript
    assert 'localStorage.setItem' in i18n_javascript
    assert 'return SUPPORTED.has(saved) ? saved : "en"' in i18n_javascript
    assert "mountSelector(document.querySelector('.hero-tools'))" in review_html
    assert "mountSelector(document.querySelector('.hero-tools'))" in versions_html
    assert "repeat(3,minmax(0,1fr))" in review_html
    assert "tr('pageDeleted')" not in review_html
    assert "value&&$('project').selectedOptions[0]?.textContent)||tr('allProjects')" in review_html
    assert "${esc(tr('allProjects'))}" in review_html
    assert "${esc(tr('allSkills'))}" in review_html
    assert "language=window.ForgeI18n?.language||'zh-CN'" in review_html
    assert "fetch('/api/summary-generation-estimate?'" in review_html
    assert "fetch('/api/summary-generation'" in review_html
    assert "estimate.sourceCount" in review_html
    assert "estimate.evidenceBytes" in review_html
    assert "estimate.estimatedMapBatches" in review_html
    assert "发送给已配置的 LLM" in review_html
    assert "$('llm-model')" not in review_html
    assert "fetch('/api/summary-generation-retry'" in review_html
    assert "pollSummaryJob" in review_html
    assert "summaryPollSequence" in review_html
    assert "[data-refine]" not in versions_html
    assert "'/api/refine'" not in versions_html
    assert "forge-skill-training-summary-v6" in versions_html
    assert '<option value="PRE_CHECK"' in versions_html
    assert '<option value="FINAL_VALIDATION"' in versions_html
    assert '<option value="PENDING"' in versions_html
    assert '<option value="CONFIRMED"' in versions_html
    assert '<option value="EXCLUDED"' in versions_html
    assert "'执行前检查':'Pre-check'" in versions_html
    assert "'待审核':'Pending'" in versions_html
    assert 'data-overlay-select' in versions_html
    assert "ai&&state==='REVIEWED'&&confirmed" in versions_html
    assert "data-evidence-more" in versions_html
    assert 'type="radio" name="overlay-summary"' in versions_html
    assert "modern&&state==='REVIEWED'" not in versions_html
    assert "tag?.textContent==='REVIEWED'" not in versions_html
    assert 'class="danger" data-delete' in versions_html
    assert "[data-delete]" in versions_html
    assert "if(!card)" in versions_html
    assert "overlayButton.disabled=selected!==1" in versions_html
    assert "language=window.ForgeI18n?.language||'en'" in versions_html
    assert "'Skill 汇总管理':'Skill Summary Management'" in versions_html
    assert 'href="/overlays"' in review_html
    assert 'href="/overlays"' in versions_html
    assert 'id="overlays"' not in versions_html
    assert 'id="overlays"' in overlays_html
    assert 'href="/versions"' in overlays_html
    assert "'/api/review-overlay'" in overlays_html
    assert "'/api/copy-overlay'" in overlays_html
    assert "generatedOverlayDraftHint" in overlays_html
    assert "manualCopyDraftHint" in overlays_html
    assert "'/api/evaluate-publish-overlay'" in overlays_html
    assert "'/api/activate-overlay'" in overlays_html
    assert "'/api/disable-overlay'" in overlays_html
    assert "'/api/delete-overlay'" in overlays_html
    assert 'overlayPageTitle' in i18n_javascript
    assert 'id="hook-config"' in review_html
    assert "fetch('/api/hook-status')" in review_html
    assert "'/api/hook-config'" in review_html
    assert 'name="hook-host"' in review_html
    assert 'hookConfiguration' in i18n_javascript
    assert 'id="latest-record-evidence"' in review_html
    assert "record.hook_captured_at?'hookCaptured'" in review_html
    assert "status.lastEvent?.outcome" in review_html
    assert "receipt?.invocationIds?.includes(record.invocation_id)" in review_html
    assert "record.metadata?.hookCapture" in review_html
    assert "profile?.matchedSkills?.length" in review_html
    assert "sharedReviewGroup" in review_html
    assert "r.shared_review_group_id" in review_html
    assert "hookOnlyAuxiliary" in review_html
    assert "value.updatedCount>1" in review_html
    assert "sharedReviewApplied" in i18n_javascript
    assert "sharedCapturePending" in review_html
    assert "sharedCapturePending" in i18n_javascript
    assert "status.trustStatus==='MANUAL_CHECK_REQUIRED'" in review_html
    assert "status.eventScope==='HISTORICAL'" in review_html
    assert 'type="checkbox" name="hook-host"' in review_html
    assert "value.configuredHosts" in review_html
    assert "updateHook(input.value,input.checked)" in review_html
    assert 'hookNoInvocation' in i18n_javascript
    assert 'id="codex-trust-reminder" class="hook-trust-reminder" hidden' in review_html
    assert 'data-i18n="codexTrustHint"' in review_html
    assert 'data-i18n="codexTrustSummary"' in review_html
    assert '如尚未信任 Codex Hook，请在 Codex Desktop 中确认' in i18n_javascript
    assert 'If the Codex Hook is not yet trusted, confirm it in Codex Desktop' in i18n_javascript
    assert "$('codex-trust-reminder').hidden=!(hosts||[]).includes('codex')" in review_html
    assert "const trust=host!=='codex'?'':status.trustStatus" in review_html
    assert 'hookCapabilityText(status,host)' in review_html
    assert 'claudeTrustTitle' not in i18n_javascript
    assert 'claudeTrustNote' not in i18n_javascript
    assert 'cursorTrustTitle' not in i18n_javascript
    assert 'cursorTrustNote' not in i18n_javascript
    assert 'data-guidance-host' not in review_html
    assert "Forge Hooks for all three hosts can be enabled together" in i18n_javascript
    assert "hookHostsActive" in i18n_javascript
    assert "switchHookConfirm" not in i18n_javascript
    assert 'Select a project to inspect and configure its Hook.' not in i18n_javascript
    assert 'Remove project Hook' not in i18n_javascript


def test_hook_status_is_global(monkeypatch):
    observed = {}

    def status(forge_root):
        observed["forgeRoot"] = forge_root
        return {"configuredHosts": ["codex", "cursor"], "hosts": {}}

    monkeypatch.setattr(review_server, "global_hook_status", status)

    result = review_server.hook_status()

    assert result["configuredHosts"] == ["codex", "cursor"]
    assert observed == {"forgeRoot": review_server.FORGE_ROOT}


def test_global_hook_configuration_validates_host_and_supports_removal(monkeypatch):
    calls = []
    monkeypatch.setattr(
        review_server,
        "configure_global_hook",
        lambda forge_root, host: calls.append(("configure", forge_root, host))
        or {"host": host, "configuredHosts": [host], "state": "CONFIGURED"},
    )
    monkeypatch.setattr(
        review_server,
        "remove_global_hook",
        lambda forge_root, host: calls.append(("remove", forge_root, host))
        or {"host": host, "configuredHosts": [], "state": "NOT_CONFIGURED"},
    )

    configured = review_server.update_global_hook({
        "action": "CONFIGURE", "host": "claude-code",
    })
    removed = review_server.update_global_hook({
        "action": "REMOVE", "host": "claude-code",
    })

    assert configured["configuredHosts"] == ["claude-code"]
    assert removed["configuredHosts"] == []
    assert calls == [
        ("configure", review_server.FORGE_ROOT, "claude-code"),
        ("remove", review_server.FORGE_ROOT, "claude-code"),
    ]
    with pytest.raises(ValueError, match="host must be"):
        review_server.update_global_hook({
            "action": "CONFIGURE", "host": "unknown",
        })
    with pytest.raises(ValueError, match="host must be"):
        review_server.update_global_hook({"action": "REMOVE"})
def test_refinement_labels_cover_specialized_skills_and_known_failure():
    cases = json.loads((REPOSITORY_ROOT / "forge" / "evals" / "summary-refinement-cases.json").read_text(encoding="utf-8"))
    assert {"KEEP", "DISCARD", "CONFLICT"} <= {case["expectedDecision"] for case in cases["cases"]}
    assert {case["skill"] for case in cases["cases"]} <= set(SKILL_CRITERIA)
    assert any(case["id"] == "explain-ui-state" and case["expectedDecision"] == "DISCARD" for case in cases["cases"])
def test_summary_decisions_get_routes_query(monkeypatch):
    handler = object.__new__(review_server.Handler)
    handler.path = "/api/summary-decisions?project=p&skill=plan&version=1&page=2"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.server = SimpleNamespace(server_port=8765)
    responses = []
    handler.send_json = lambda value, status=200: responses.append((value, status))
    monkeypatch.setattr(review_server, "summary_decisions", lambda query: {"query": query})
    handler.do_GET()
    assert responses == [({"query": {"project": ["p"], "skill": ["plan"], "version": ["1"], "page": ["2"]}}, 200)]


def test_summary_decisions_preserve_all_stages_sources_and_pagination(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id="project-decisions", source_ids=["r1", "r2"])
        connection.execute("DELETE FROM summary_generation_batches WHERE job_id = 'job-1'")
        batches = [
            ("MAP", 0, {"recordDecisions": [
                {"recordId": "r1", "decision": "KEEP", "reason": "Reusable"},
                {"recordId": "r2", "decision": "CONFLICT", "reason": "Contradictory evidence"},
            ], "candidates": [{"id": "map-1", "sourceRecordIds": ["r1"]}]}),
            ("REDUCE", 1, {"decisions": [
                {"candidateId": "map-1", "decision": "DISCARD", "reason": "Too specific"},
            ], "candidates": []}),
        ]
        for phase, level, result in batches:
            connection.execute(
                "INSERT INTO summary_generation_batches "
                "(job_id,phase,level,batch_index,input_digest,status,item_count,result_json,created_at) "
                "VALUES ('job-1',?,?,0,'digest','SUCCEEDED',1,?,'now')",
                (phase, level, json.dumps(result)),
            )
    connection.close()
    _configure_overlay_project(monkeypatch, "project-decisions", project, database)
    query = {"project": ["project-decisions"], "skill": ["code-review"], "version": ["1"], "limit": ["2"]}
    first = review_server.summary_decisions(query)
    second = review_server.summary_decisions({**query, "page": ["2"]})
    assert first["total"] == 3 and first["hasMore"] is True
    assert first["decisions"][1]["decision"] == "CONFLICT"
    assert first["decisions"][1]["reason"] == "Contradictory evidence"
    assert first["decisions"][1]["sourceRecordIds"] == ["r2"]
    assert second["decisions"][0]["phase"] == "REDUCE"
    assert second["decisions"][0]["sourceRecordIds"] == ["r1"]
    assert second["decisions"][0]["reason"] == "Too specific"
    assert second["hasMore"] is False
    with pytest.raises(ValueError, match="summary version not found"):
        review_server.summary_decisions({**query, "version": ["2"]})


def test_summary_decisions_resolve_final_candidate_to_all_sources(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "learning.sqlite"
    sources = [f"r{index}" for index in range(25)]
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(connection, project_id="project-decisions", source_ids=sources)
        connection.execute("DELETE FROM summary_generation_batches WHERE job_id = 'job-1'")
        results = [
            ("MAP", 0, {"recordDecisions": [{"recordId": rid, "decision": "KEEP", "reason": "Reusable"} for rid in sources],
                        "candidates": [{"id": "map-1", "sourceRecordIds": sources}]}),
            ("REDUCE", 1, {"decisions": [{"candidateId": "map-1", "decision": "KEEP", "reason": "Merge"}],
                           "candidates": [{"id": "reduce-1", "sourceRecordIds": sources}]}),
            ("FINAL", 2, {"decisions": [{"candidateId": "reduce-1", "decision": "CONFLICT", "reason": "Needs review"}], "rules": []}),
        ]
        for phase, level, result in results:
            connection.execute(
                "INSERT INTO summary_generation_batches "
                "(job_id,phase,level,batch_index,input_digest,status,item_count,result_json,created_at) "
                "VALUES ('job-1',?,?,0,'digest','SUCCEEDED',1,?,'now')", (phase, level, json.dumps(result)),
            )
    connection.close()
    _configure_overlay_project(monkeypatch, "project-decisions", project, database)
    result = review_server.summary_decisions({"project": ["project-decisions"], "skill": ["code-review"], "version": ["1"], "limit": ["100"]})
    assert result["decisions"][-1]["phase"] == "FINAL"
    assert result["decisions"][-1]["sourceRecordIds"] == sources


def test_v6_summary_evidence_uses_complete_persisted_lineage(tmp_path, monkeypatch):
    project_id = "project-complete-evidence"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "evidence.sqlite"
    source_ids = [f"record-{index:02d}" for index in range(25)]
    full_rule = {
        "id": "rule-many-sources",
        "stage": "FINAL_VALIDATION",
        "status": "CONFIRMED",
        "trigger": "Before returning the result",
        "instruction": "Check all accumulated evidence.",
        "verification": "Verify the complete persisted source lineage.",
        "sourceRecordIds": source_ids,
        "supportCount": len(source_ids),
        "sourceIdsTruncated": False,
    }
    visible_rule = dict(full_rule)
    visible_rule["sourceRecordIds"] = source_ids[:20]
    visible_rule["sourceIdsTruncated"] = True
    connection = connect_database(database)
    with connection:
        _insert_releasable_v6_summary(
            connection, project_id=project_id, rules=[visible_rule],
            source_ids=source_ids, final_rules=[full_rule],
        )
    connection.close()
    _configure_overlay_project(monkeypatch, project_id, project, database)

    first = review_server.summary_evidence({
        "project": [project_id], "skill": ["code-review"], "version": ["1"],
        "page": ["1"], "limit": ["20"],
    })
    second = review_server.summary_evidence({
        "project": [project_id], "skill": ["code-review"], "version": ["1"],
        "page": ["2"], "limit": ["20"],
    })

    assert [record["recordId"] for record in first["records"]] == source_ids[:20]
    assert [record["recordId"] for record in second["records"]] == source_ids[20:]
    assert first | {"records": []} == {
        "records": [], "page": 1, "pageSize": 20, "total": 25, "hasMore": True,
    }
    assert second["hasMore"] is False
    assert all(
        record["ruleIds"] == ["rule-many-sources"]
        for record in [*first["records"], *second["records"]]
    )
def test_overlay_preserves_refined_trigger_and_verification():
    content = review_server._overlay_content("plan", [{"stage": "PRE_CHECK",
        "trigger": "When a plan spans multiple phases", "instruction": "List the phase dependencies.",
        "verification": "Each phase has a verifiable completion condition.",
        "antiPattern": "Do not substitute task facts for reusable checks."}], "en")
    assert "When a plan spans multiple phases: List the phase dependencies." in content
    assert "Verify: Each phase has a verifiable completion condition." in content
    assert "Avoid: Do not substitute task facts" in content


def test_refinement_reads_effective_reviewed_evidence_and_rejects_overlong_record(tmp_path):
    database = tmp_path / "evidence.sqlite"
    with closing(connect_database(database)) as connection, connection:
        connection.execute("INSERT INTO learning_summaries (id,project_id,skill,version,created_at,source_count,summary_json,lifecycle_status) VALUES ('summary','project','plan',1,'now',1,'{}','DRAFT')")
        connection.execute("INSERT INTO learning_records (id,project_id,project_name,project_path,skill,run_id,captured_at,output_json,edited_content,review_note) VALUES ('record','project','project','/project','plan','run-1','now','\"old\"','\"edited\"','approved')")
        connection.execute("INSERT INTO learning_summary_sources (summary_id,record_id) VALUES ('summary','record')")
        candidate = [{"id": "candidate", "sourceRecordIds": ["record"]}]
        assert evidence_packet(connection, "summary", "project", "plan", candidate)["records"][0]["effectiveContent"] == "edited"
        connection.execute("UPDATE learning_records SET edited_content = ? WHERE id = 'record'", ("x" * 17000,))
        with pytest.raises(ValueError, match="evidence budget"):
            evidence_packet(connection, "summary", "project", "plan", candidate)
        with pytest.raises(ValueError, match="truncated"):
            evidence_packet(connection, "summary", "project", "plan",
                            [{**candidate[0], "sourceIdsTruncated": True}])
def test_llm_http_error_preserves_bounded_provider_diagnostics(monkeypatch):
    provider_body = json.dumps({"error": {
        "message": "This account only allows Codex official clients; token=test-key",
        "type": "forbidden_error", "code": "client_restricted",
    }}).encode("utf-8")
    error = urllib.error.HTTPError(
        "https://example.test/v1/responses", 403, "Forbidden",
        {"x-request-id": "request-123"}, io.BytesIO(provider_body),
    )
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmProviderError) as captured:
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})

    message = str(captured.value)
    assert "HTTP 403 Forbidden" in message
    assert "message=This account only allows Codex official clients; token=[REDACTED]" in message
    assert "type=forbidden_error" in message
    assert "code=client_restricted" in message
    assert "requestId=request-123" in message
    assert "test-key" not in message


@pytest.mark.parametrize("error", [TimeoutError(), socket.timeout()])
def test_llm_timeout_reports_configured_budget(monkeypatch, error):
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmTimeoutError, match="timed out after 60 seconds"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_llm_transport_error_preserves_failure_category(monkeypatch):
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.URLError(ConnectionResetError("reset"))
        ),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmTransportError, match="ConnectionResetError"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_llm_invalid_json_response_is_distinct(monkeypatch):
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(b"not-json"),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(ValueError, match="invalid JSON response"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_responses_stream_accumulates_deltas_and_usage(monkeypatch):
    events = (
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"hel"}\n\n'
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"lo"}\n\n'
        'event: response.completed\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":7,'
        '"output_tokens":2,"total_tokens":9},"output":[]}}\n\n'
    ).encode("utf-8")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout, json.loads(request.data.decode("utf-8"))))
        return _FakeStreamingResponse(events)

    monkeypatch.setattr(review_server.urllib.request, "urlopen", fake_urlopen)
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    content, usage = review_server._call_llm(
        config, "test-key", "instruction", {"message": "hello"}
    )

    assert content == "hello"
    assert usage == {
        "status": "reported", "inputTokens": 7, "outputTokens": 2, "totalTokens": 9,
    }
    assert calls[0][1] == 60
    assert "stream" not in calls[0][2]
    assert calls[0][0].get_header("Accept") is None


def test_responses_stream_surfaces_failed_event_without_leaking_key(monkeypatch):
    events = (
        'event: response.failed\n'
        'data: {"type":"response.failed","response":{"error":'
        '{"message":"upstream rejected test-key","type":"forbidden_error",'
        '"code":"upstream_error"}}}\n\n'
    ).encode("utf-8")
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeStreamingResponse(events),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmProviderError) as captured:
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})

    message = str(captured.value)
    assert "response.failed" in message
    assert "message=upstream rejected [REDACTED]" in message
    assert "type=forbidden_error" in message
    assert "code=upstream_error" in message
    assert "test-key" not in message


def test_responses_stream_surfaces_top_level_error_details(monkeypatch):
    events = (
        'event: error\n'
        'data: {"type":"error","message":"relay unavailable",'
        '"code":"relay_error"}\n\n'
    ).encode("utf-8")
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeStreamingResponse(events),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmProviderError) as captured:
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})

    message = str(captured.value)
    assert "error" in message
    assert "message=relay unavailable" in message
    assert "code=relay_error" in message


def test_responses_stream_rejects_oversized_completed_output(monkeypatch):
    completed = {
        "type": "response.completed",
        "response": {"output_text": "x" * (review_server.MAX_LLM_RESPONSE_BYTES + 1)},
    }
    events = f"data: {json.dumps(completed)}\n\n".encode("utf-8")
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeStreamingResponse(events),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(ValueError, match="256 KB"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_responses_stream_enforces_total_duration_after_blocking_read(monkeypatch):
    events = (
        'data: {"type":"response.output_text.delta","delta":"late"}\n\n'
    ).encode("utf-8")
    clock = iter((0.0, 0.0, review_server.MAX_LLM_STREAM_DURATION_SECONDS + 1.0))
    monkeypatch.setattr(review_server.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeStreamingResponse(events),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(review_server.LlmTimeoutError, match="exceeded 180 seconds"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_responses_stream_requires_completed_event(monkeypatch):
    events = (
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
    ).encode("utf-8")
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeStreamingResponse(events),
    )
    config = {
        "endpoint": "https://example.test/v1/responses", "model": "test-model",
        "wireApi": "responses", "timeoutSeconds": 60,
    }

    with pytest.raises(ValueError, match="without a response.completed event"):
        review_server._call_llm(config, "test-key", "instruction", {"message": "hello"})


def test_save_llm_config_writes_complete_json_atomically(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    monkeypatch.setattr(review_server, "_environment_value", lambda _name: "test-key")
    saved = review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    assert saved["configured"] is True
    assert saved["baseUrl"] == "https://example.test/v1"
    assert saved["requestUrl"] == "https://example.test/v1/responses"
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["wireApi"] == "responses"
    assert persisted["baseUrl"] == "https://example.test/v1"
    assert "endpoint" not in persisted
    assert not config_path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(("configured_url", "wire_api", "expected"), [
    ("https://example.test/v1", "responses", "https://example.test/v1/responses"),
    ("https://example.test/v1/", "chat_completions", "https://example.test/v1/chat/completions"),
    ("https://example.test/v1/responses", "responses", "https://example.test/v1/responses"),
    ("https://example.test/v1/chat/completions", "responses", "https://example.test/v1/responses"),
])
def test_llm_request_url_appends_wire_api_without_duplicate_suffix(
    configured_url, wire_api, expected,
):
    assert review_server._llm_request_url({
        "baseUrl": configured_url, "wireApi": wire_api,
    }) == expected


def test_llm_config_migrates_legacy_full_endpoint_in_memory(tmp_path, monkeypatch):
    config_path = tmp_path / "llm-refiner.json"
    config_path.write_text(json.dumps({
        "enabled": True, "endpoint": "https://example.test/v1/chat/completions",
        "model": "test-model", "wireApi": "chat_completions", "apiKeyEnv": "TEST_KEY",
    }), encoding="utf-8")
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)

    loaded = review_server.llm_config()

    assert loaded["baseUrl"] == "https://example.test/v1"
    assert "endpoint" not in loaded
    assert review_server._llm_request_url(loaded) == "https://example.test/v1/chat/completions"


def test_llm_endpoints_reject_non_object_and_malformed_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"enabled": True, "apiKeyEnv": None}), encoding="utf-8")
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    assert review_server.llm_config_status()["configured"] is False
    with pytest.raises(ValueError, match="JSON object"):
        review_server.save_llm_config([])


@pytest.mark.parametrize("registry_value", [None, [], "invalid", {"projects": {}}])
def test_projects_rejects_structurally_invalid_registry(tmp_path, monkeypatch, registry_value):
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps(registry_value), encoding="utf-8")
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry)

    assert review_server.projects() == []


def test_review_mutations_require_same_origin_json_service_cookie(monkeypatch):
    monkeypatch.setattr(review_server, "SERVICE_TOKEN", "test-token")
    valid = {
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:8765",
        "Content-Type": "application/json; charset=utf-8",
        "Cookie": f"{review_server.SERVICE_COOKIE}=test-token",
    }

    assert review_server._mutation_request_error(valid, 8765) is None
    assert review_server._mutation_request_error({**valid, "Cookie": ""}, 8765)[0] == 403
    assert review_server._mutation_request_error(
        {**valid, "Origin": "https://attacker.example"}, 8765
    )[0] == 403
    assert review_server._mutation_request_error({**valid, "Host": "localhost:8765"}, 8765)[0] == 403
    assert review_server._mutation_request_error({**valid, "Content-Type": "text/plain"}, 8765)[0] == 415
    assert "HttpOnly" in review_server._service_cookie()
    assert "SameSite=Strict" in review_server._service_cookie()


def test_delete_overlay_removes_its_evaluation_artifacts(tmp_path, monkeypatch):
    project_id = "project-delete-artifact"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    try:
        connection.execute(
            "INSERT INTO skill_overlays "
            "(id, project_id, skill, version, status, content, manifest_json, content_digest, created_at) "
            "VALUES ('overlay-delete-me', ?, 'code-review', 1, 'DISABLED', 'content', '{}', 'digest', 'now')",
            (project_id,),
        )
        connection.commit()
    finally:
        connection.close()
    evaluations = database.parent / "evaluations"
    evaluations.mkdir()
    owned = evaluations / "overlay-v1-overlay-delete-me-abc.json"
    unrelated = evaluations / "overlay-v1-overlay-keep-abc.json"
    owned.write_text("{}", encoding="utf-8")
    unrelated.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project),
        "database": str(database),
    }])
    result = review_server.delete_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": "overlay-delete-me",
    })
    assert result["deleted"] is True
    assert not owned.exists()
    assert unrelated.exists()


def test_record_page_reuses_one_project_registry_snapshot(monkeypatch):
    calls = 0

    def project_snapshot():
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(review_server, "projects", project_snapshot)
    page = review_server.query_record_page({"page": ["1"]})

    assert page == {
        "items": [], "page": 1, "pageSize": 20, "total": 0, "hasMore": False,
        "projects": [],
    }
    assert calls == 1


def test_record_page_opens_each_database_once_for_rows_and_count(tmp_path, monkeypatch):
    project_items = []
    for index in range(3):
        project = tmp_path / f"project-{index}"
        project.mkdir()
        database = tmp_path / f"learning-{index}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at, output_json)
                   VALUES (?, ?, ?, ?, 'code-review', ?, '{}')""",
                (f"record-{index}", f"project-{index}", project.name, str(project),
                 f"2026-09-15T00:00:0{index}Z"),
            )
        connection.close()
        project_items.append({
            "projectId": f"project-{index}", "name": project.name, "path": str(project),
            "database": str(database), "status": "ACTIVE",
        })
    monkeypatch.setattr(review_server, "projects", lambda: project_items)
    original_connect = review_server.sqlite3.connect
    connection_count = 0

    def counted_connect(*args, **kwargs):
        nonlocal connection_count
        connection_count += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(review_server.sqlite3, "connect", counted_connect)

    page = review_server.query_record_page({"page": ["1"]})

    assert page["total"] == 3
    assert page["projects"] == project_items
    assert connection_count == len(project_items)
    for item in project_items:
        Path(item["database"]).rename(Path(item["database"]).with_suffix(".closed"))


def test_record_page_migrates_old_database_before_searching_host_output(tmp_path, monkeypatch):
    project = tmp_path / "old-project"
    project.mkdir()
    database = tmp_path / "old-learning.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE learning_records (
           id TEXT PRIMARY KEY, project_id TEXT, project_name TEXT, project_path TEXT,
           skill TEXT, run_id TEXT, stage TEXT, run_status TEXT, captured_at TEXT,
           output_json TEXT, diagnostics_json TEXT, metadata_json TEXT, evaluation_json TEXT,
           review_status TEXT, reviewed INTEGER, edited_content TEXT, review_note TEXT,
           reviewed_at TEXT, deleted_at TEXT)"""
    )
    connection.execute(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, captured_at, output_json,
            review_status, reviewed, review_note)
           VALUES ('old', 'project-old', 'old', ?, 'code-review',
                   '2026-09-15T00:00:00Z', '{"conclusion":"legacy"}', 'ACTIVE', 0, '')""",
        (str(project),),
    )
    connection.commit()
    connection.close()
    projects = [{
        "projectId": "project-old", "name": "old", "path": str(project),
        "database": str(database), "status": "ACTIVE",
    }]
    monkeypatch.setattr(review_server, "projects", lambda: projects)

    page = review_server.query_record_page({"page": ["1"], "q": ["legacy"]})

    assert page["total"] == 1
    assert page["items"][0]["host_output"] is None


def test_project_health_transition_is_persisted_only_when_changed(tmp_path, monkeypatch):
    project = tmp_path / "missing-database-project"
    project.mkdir()
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps({"projects": [{
        "projectId": "project-health", "name": "health", "path": str(project),
        "database": str(project / "missing.sqlite"), "status": "ACTIVE",
    }]}), encoding="utf-8")
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry)
    writes = []
    original_write = review_server._write_registry

    def track_write(path, value):
        writes.append(path)
        original_write(path, value)

    monkeypatch.setattr(review_server, "_write_registry", track_write)

    first = review_server.projects()
    second = review_server.projects()

    assert first[0]["status"] == "UNAVAILABLE"
    assert first[0]["healthReason"] == "learning database unavailable"
    assert first[0]["unavailableSince"]
    assert second == first
    assert writes == [registry]
    persisted = json.loads(registry.read_text(encoding="utf-8"))["projects"][0]
    assert persisted["status"] == "UNAVAILABLE"
    assert persisted["healthReason"] == "learning database unavailable"


def test_project_registration_can_be_archived_and_restored_without_deleting_data(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    connection.close()
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps({"projects": [{
        "projectId": "project-archive", "name": "archive", "path": str(project),
        "database": str(database), "status": "ACTIVE",
    }]}), encoding="utf-8")
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry)

    archived = review_server.set_project_registration_status({
        "projectId": "project-archive", "action": "ARCHIVE",
    })
    assert archived["status"] == "DISABLED"
    assert database.is_file()
    assert json.loads(registry.read_text(encoding="utf-8"))["projects"][0]["status"] == "DISABLED"

    restored = review_server.set_project_registration_status({
        "projectId": "project-archive", "action": "RESTORE",
    })
    assert restored["status"] == "ACTIVE"
    assert restored["healthReason"] is None
    assert database.is_file()


def test_restore_does_not_treat_missing_project_path_as_current_directory(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    connection.close()
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps({"projects": [{
        "projectId": "project-no-path", "name": "no-path", "database": str(database),
        "status": "DISABLED",
    }]}), encoding="utf-8")
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry)

    restored = review_server.set_project_registration_status({
        "projectId": "project-no-path", "action": "RESTORE",
    })

    assert restored["status"] == "UNAVAILABLE"
    assert restored["healthReason"] == "project path unavailable"


def test_project_status_change_rejects_ambiguous_conflicting_identity(tmp_path, monkeypatch):
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps({"projects": [
        {"projectId": "duplicate", "status": "CONFLICT", "database": "one.sqlite"},
        {"projectId": "duplicate", "status": "CONFLICT", "database": "two.sqlite"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry)

    with pytest.raises(ValueError, match="conflicting project identity"):
        review_server.set_project_registration_status({
            "projectId": "duplicate", "action": "ARCHIVE",
        })


def test_default_record_queries_skip_archived_projects_but_explicit_filter_can_inspect_them(
        tmp_path, monkeypatch):
    project_items = []
    for project_id, status in (("active-project", "ACTIVE"), ("archived-project", "DISABLED")):
        project = tmp_path / project_id
        project.mkdir()
        database = tmp_path / f"{project_id}.sqlite"
        connection = connect_database(database)
        with connection:
            connection.execute(
                """INSERT INTO learning_records
                   (id, project_id, project_name, project_path, skill, captured_at, output_json)
                   VALUES (?, ?, ?, ?, 'code-review', '2026-09-15T00:00:00Z', '{\"result\":\"ok\"}')""",
                (f"record-{project_id}", project_id, project_id, str(project)),
            )
        connection.close()
        project_items.append({
            "projectId": project_id, "name": project_id, "path": str(project),
            "database": str(database), "status": status,
        })
    monkeypatch.setattr(review_server, "projects", lambda: project_items)

    default_page = review_server.query_record_page({"page": ["1"]})
    archived_page = review_server.query_record_page({
        "page": ["1"], "project": ["archived-project"],
    })

    assert default_page["total"] == 1
    assert [item["id"] for item in default_page["items"]] == ["record-active-project"]
    assert archived_page["total"] == 1
    assert [item["id"] for item in archived_page["items"]] == ["record-archived-project"]
