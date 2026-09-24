from __future__ import annotations

import hashlib
import io
import json
import socket
import sqlite3
import sys
import urllib.error
from contextlib import closing
from types import SimpleNamespace
from pathlib import Path

import pytest


@pytest.mark.parametrize("path", ["/", "/api/service", "/api/records", "/api/projects"])
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


def test_summary_extraction_allows_writes_but_rejects_changed_evidence(tmp_path, monkeypatch):
    database = tmp_path / "summary.sqlite"
    connection = connect_database(database)
    with connection:
        connection.execute(
            "INSERT INTO learning_records (id, project_id, project_name, project_path, skill, captured_at, output_json, reviewed) "
            "VALUES ('record', 'project-snapshot', 'project', ?, 'code-review', ?, ?, 1)",
            (str(tmp_path), review_server.now(), json.dumps({"findings": [{"title": "Check transactions", "suggested_direction": "Verify write locks"}]})),
        )
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": "project-snapshot", "name": "project", "path": str(tmp_path), "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    original_build = review_server.build_summary

    def concurrent_build(records, **kwargs):
        with closing(sqlite3.connect(database, timeout=0)) as other, other:
            other.execute("UPDATE learning_records SET review_note = 'changed' WHERE id = 'record'")
        return original_build(records, **kwargs)

    monkeypatch.setattr(review_server, "build_summary", concurrent_build)
    with pytest.raises(ValueError, match="source evidence changed"):
        review_server.create_summary({"projectId": "project-snapshot", "skill": "code-review"})
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0


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
from forge_cli.learning_collector import _adopt_copied_database, connect_database
from summary_engine import build_code_review_summary, build_generic_summary, build_summary, encoded_size
from refinement_quality import SKILL_CRITERIA, evidence_packet, validate_decisions, validate_rules


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


def test_code_review_summary_clusters_related_findings_and_stays_compact():
    records = [
        {"recordId": "r1", "capturedAt": "2026-09-01T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("项目注册表的读改写没有并发保护，可能丢失注册项目", "使用跨平台文件锁保护注册表读改写。")]}},
        {"recordId": "r2", "capturedAt": "2026-09-02T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("注册表锁仅限单个 Python 进程，跨进程仍可能丢失项目", "使用跨平台文件锁或 SQLite registry。")]}},
        {"recordId": "r3", "capturedAt": "2026-09-03T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("项目身份文件初始化不受注册锁保护", "将 project.json 初始化放入同一个跨进程锁。")]}},
        {"recordId": "r4", "capturedAt": "2026-09-04T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("汇总响应体没有大小上限", "限制汇总响应体大小并按需读取详情。", "Medium")]}},
    ]

    summary = build_code_review_summary(records)

    assert summary["statistics"]["originalFindings"] == 4
    assert summary["statistics"]["candidateClusters"] == 3
    assert summary["rules"][0]["supportCount"] == 2
    assert summary["rules"][0]["sourceRecordIds"] == ["r1", "r2"]
    assert all(rule["status"] == "PENDING" for rule in summary["rules"])
    assert encoded_size(summary) < 20_000
    assert "findings" not in summary


def test_code_review_summary_does_not_merge_unrelated_findings_with_generic_prefixes():
    records = [{
        "recordId": "r1", "capturedAt": "2026-09-01T00:00:00Z", "content": {"findings": [
            finding("Missing authorization check in delete endpoint", "Validate delete permission."),
        ]},
    }, {
        "recordId": "r2", "capturedAt": "2026-09-02T00:00:00Z", "content": {"findings": [
            finding("Missing transaction around database update", "Wrap the update in a transaction."),
        ]},
    }]

    summary = build_code_review_summary(records)

    assert summary["statistics"]["candidateClusters"] == 2
    assert all(rule["supportCount"] == 1 for rule in summary["rules"])


def test_code_review_summary_keeps_conflicting_directions_separate():
    records = [
        {"recordId": "r1", "capturedAt": "2026-09-01T00:00:00Z", "content": {"findings": [
            finding("Timeout should be adjusted", "Increase the timeout to 30 seconds."),
        ]}},
        {"recordId": "r2", "capturedAt": "2026-09-02T00:00:00Z", "content": {"findings": [
            finding("Timeout should be adjusted", "Do not increase the timeout; fix cancellation."),
        ]}},
    ]

    summary = build_code_review_summary(records)

    assert summary["statistics"]["candidateClusters"] == 2
    assert {rule["instruction"] for rule in summary["rules"]} == {
        "Increase the timeout to 30 seconds.", "Do not increase the timeout; fix cancellation.",
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


def test_copied_database_resets_active_overlay_to_draft(tmp_path):
    database = tmp_path / "copied.sqlite"
    project = tmp_path / "copied-project"
    project.mkdir()
    connection = connect_database(database)
    try:
        connection.execute(
            "INSERT INTO skill_overlays "
            "(id, project_id, skill, version, status, content, manifest_json, content_digest, created_at, enabled_at) "
            "VALUES ('overlay-1', 'project-old', 'code-review', 1, 'ACTIVE', '# v1', '{}', 'sha256:1', "
            "'2026-09-14T00:00:00Z', '2026-09-14T00:00:00Z')"
        )
        connection.commit()
    finally:
        connection.close()

    _adopt_copied_database(
        database,
        "project-old",
        {"projectId": "project-new", "name": "copied-project"},
        project,
    )

    connection = connect_database(database)
    try:
        overlay = connection.execute(
            "SELECT project_id, status, enabled_at, disabled_at, evaluation_json, published_at, manifest_json "
            "FROM skill_overlays WHERE id = 'overlay-1'"
        ).fetchone()
        assert overlay[0] == "project-new"
        assert overlay[1] == "DRAFT"
        assert overlay[2] is None
        assert overlay[3] is None
        assert overlay[4] is None and overlay[5] is None
        assert json.loads(overlay[6])["projectId"] == "project-new"
    finally:
        connection.close()


def test_copied_overlay_sources_are_rebased_and_require_fresh_review(tmp_path):
    database = tmp_path / "copied.sqlite"
    project = tmp_path / "copied-project"
    project.mkdir()
    connection = connect_database(database)
    summary = {"format": "forge-skill-training-summary-v5", "projectId": "project-old",
               "status": "REVIEWED", "rules": [{"id": "rule-1", "status": "CONFIRMED"}]}
    summary_json = json.dumps(summary)
    old_digest = "sha256:" + hashlib.sha256(summary_json.encode()).hexdigest()
    manifest = {"projectId": "project-old", "skill": "code-review", "executionSource": "content",
                "rules": [{"instruction": "Check the evidence"}]}
    content = "Check the evidence"
    digest = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    with connection:
        connection.execute(
            "INSERT INTO learning_summaries (id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
            "VALUES ('summary-1', 'project-old', 'code-review', 1, 'now', 0, ?, 'REVIEWED')",
            (summary_json,),
        )
        connection.execute(
            "INSERT INTO skill_overlays (id, project_id, skill, version, status, content, manifest_json, "
            "content_digest, created_at, reviewed_at, enabled_at, evaluation_json, published_at) "
            "VALUES ('overlay-1', 'project-old', 'code-review', 1, 'ACTIVE', ?, ?, ?, 'now', 'now', 'now', '{}', 'now')",
            (content, json.dumps(manifest), digest),
        )
        connection.execute(
            "INSERT INTO skill_overlay_sources (overlay_id, summary_id, summary_digest) VALUES ('overlay-1', 'summary-1', ?)",
            (old_digest,),
        )
    connection.close()

    _adopt_copied_database(database, "project-old", {"projectId": "project-new", "name": "copied"}, project)

    connection = connect_database(database)
    try:
        row = connection.execute("SELECT * FROM skill_overlays WHERE id = 'overlay-1'").fetchone()
        checks = review_server._structural_overlay_evaluation(connection, row, "code-review")
        assert checks["passed"] is True
        assert row["status"] == "DRAFT"
        assert row["reviewed_at"] is None and row["evaluation_json"] is None and row["published_at"] is None
        new_summary = connection.execute("SELECT summary_json FROM learning_summaries WHERE id = 'summary-1'").fetchone()[0]
        new_digest = connection.execute("SELECT summary_digest FROM skill_overlay_sources").fetchone()[0]
        assert new_digest != old_digest
        assert new_digest == "sha256:" + hashlib.sha256(new_summary.encode()).hexdigest()
    finally:
        connection.close()


def test_create_overlay_merges_reviewed_summary_rules_into_draft(tmp_path, monkeypatch):
    project_id = "project-overlay"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    try:
        for version, rule_id, instruction in (
            (1, "rule-1", "检查 API 错误码是否稳定。"),
            (2, "rule-2", "  检查   API 错误码是否稳定。  "),
        ):
            snapshot = {
                "format": "forge-skill-training-summary-v5", "status": "REVIEWED",
                "rules": [{"id": rule_id, "stage": "FINAL_VALIDATION", "status": "CONFIRMED",
                           "instruction": instruction}],
            }
            summary_id = f"summary-{version}"
            connection.execute(
                "INSERT INTO learning_summaries "
                "(id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
                "VALUES (?, ?, 'code-review', ?, '2026-09-14T00:00:00Z', 1, ?, 'REVIEWED')",
                (summary_id, project_id, version, json.dumps(snapshot, ensure_ascii=False)),
            )
    finally:
        connection.commit()
        connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project),
                     "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})

    created = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [1, 2],
        "language": "zh-CN",
    })

    assert created["status"] == "DRAFT"
    assert created["version"] == 1
    assert created["manifest"]["summaryVersions"] == [1, 2]
    assert created["manifest"]["executionSource"] == "content"
    assert created["manifest"]["outputLanguage"] == "zh-CN"
    assert "# 项目 Overlay：code-review" in created["content"]
    assert created["content"].count("检查 API 错误码是否稳定") == 1
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT status FROM skill_overlays").fetchone()[0] == "DRAFT"
        assert check.execute("SELECT COUNT(*) FROM skill_overlay_sources").fetchone()[0] == 2
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
            "projectId": project_id, "skill": "code-review", "summaryVersions": [2, 1],
        })
    assert conflict.value.replaceable is True
    replaced = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review", "summaryVersions": [2, 1],
        "replaceExisting": True,
    })
    assert replaced["id"] == created["id"]
    assert replaced["version"] == created["version"]
    reviewed_overlay = review_server.review_overlay({
        "projectId": project_id, "skill": "skill.code_review", "overlayId": created["id"],
        "content": created["content"] + "\n- 人工补充校验。\n",
    })
    assert reviewed_overlay["status"] == "REVIEWED"
    with closing(sqlite3.connect(database)) as check, check:
        manifest = json.loads(check.execute("SELECT manifest_json FROM skill_overlays").fetchone()[0])
        assert manifest["executionSource"] == "content"
        assert manifest["contentEdited"] is True
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


def test_structural_evaluation_failure_is_persisted_as_rejected(tmp_path, monkeypatch):
    project_id = "project-structural-rejection"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "structural.sqlite"
    connection = connect_database(database)
    snapshot = {
        "format": "forge-skill-training-summary-v5", "status": "REVIEWED",
        "rules": [{"id": "rule-1", "stage": "PRE_CHECK", "status": "CONFIRMED",
                   "instruction": "Check the concrete failure path."}],
    }
    connection.execute(
        "INSERT INTO learning_summaries "
        "(id, project_id, skill, version, created_at, source_count, summary_json, lifecycle_status) "
        "VALUES ('summary-1', ?, 'code-review', 1, '2026-09-14T00:00:00Z', 1, ?, 'REVIEWED')",
        (project_id, json.dumps(snapshot)),
    )
    connection.commit()
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

def test_code_review_summary_caps_visible_source_ids_without_losing_support_count():
    records = [
        {"recordId": f"record-{index:03d}", "capturedAt": f"2026-09-01T00:00:{index:02d}Z",
         "reviewNote": "", "content": {"findings": [
             finding("并发写入没有事务保护", "检查并发写入的事务边界。")]}}
        for index in range(30)
    ]

    summary = build_code_review_summary(records)
    rule = summary["rules"][0]

    assert rule["supportCount"] == 30
    assert len(rule["sourceRecordIds"]) == 20
    assert rule["sourceIdsTruncated"] is True
    assert encoded_size(summary) < 20_000


def test_generic_summary_preserves_reviewed_content_as_pending_candidate():
    summary = build_generic_summary([
        {"recordId": "generic-1", "content": {"conclusion": "保持 API 错误码稳定。"}}
    ], skill="page-test")
    assert summary["quality"]["semanticInference"] is False
    assert summary["rules"][0]["status"] == "PENDING"
    assert "错误码" in summary["rules"][0]["instruction"]


@pytest.mark.parametrize(("skill", "content", "expected", "stage"), [
    ("debug", {
        "symptom": "保存后数据偶尔消失", "rootCause": "注册表更新缺少跨进程锁",
        "fixes": ["用同一个文件锁保护完整的读改写。"],
        "verificationPlan": "并行启动两个写入进程并验证两条记录都存在。",
    }, "文件锁", "PRE_CHECK"),
    ("implement", {
        "scope": "项目级配置保存", "decisions": ["使用临时文件替换实现原子写入。"],
        "verification": ["覆盖并发保存和无效 JSON。"],
    }, "原子写入", "PRE_CHECK"),
    ("page-test", {
        "symptom": "CI 中弹窗测试超时", "rootCause": "使用固定等待",
        "waitStrategy": "等待弹窗可见状态，不使用固定 sleep。",
        "executionResults": "目标用例连续运行三次通过。",
    }, "固定 sleep", "PRE_CHECK"),
    ("test-implementation", {
        "testScope": "Overlay 配置门禁", "scenarios": ["关闭 Skill 后不得加载 Overlay。"],
        "coverageGaps": ["尚未覆盖损坏的项目身份文件。"],
    }, "不得加载", "PRE_CHECK"),
    ("refactor", {
        "objective": "拆分汇总提取器", "transformations": ["将 Skill 画像与通用聚类逻辑分离。"],
        "behaviorPreservation": "保持所有候选默认 PENDING。",
    }, "画像", "PRE_CHECK"),
    ("explain", {
        "concept": "Overlay", "misconceptions": ["Overlay 不会替换全局 Skill。"],
        "keyPoints": ["它只增加项目级执行前检查和输出前校验。"],
    }, "不会替换", "FINAL_VALIDATION"),
    ("plan", {
        "objective": "扩展提取器", "implementationSteps": ["先增加字段画像，再补参数化测试。"],
        "validationPlan": ["运行汇总与完整 Forge 回归测试。"],
    }, "字段画像", "PRE_CHECK"),
    ("explore", {
        "currentUnderstanding": "需要选择首批提取器", "options": ["优先覆盖高频工程 Skill。"],
        "evidenceNeeded": ["检查实际启用记录和输出结构。"],
        "recommendedNextStep": "确定范围后切换到实现任务。",
    }, "高频工程", "PRE_CHECK"),
])
def test_common_skill_profiles_extract_reusable_pending_candidates(skill, content, expected, stage):
    summary = build_summary([{
        "recordId": f"record-{skill}", "capturedAt": "2026-09-15T00:00:00Z",
        "reviewNote": "人工确认", "content": content,
    }], skill=skill)

    matching = next(rule for rule in summary["rules"] if expected in rule["instruction"])
    assert matching["stage"] == stage
    assert matching["status"] == "PENDING"
    assert matching["sourceRecordIds"] == [f"record-{skill}"]
    assert summary["quality"]["summarizer"] == f"{skill}-deterministic-v1"
    assert summary["quality"]["semanticInference"] is False


def test_specialized_summary_prefers_explicit_learning_signals_and_deduplicates_fallback():
    summary = build_summary([{
        "recordId": "record-debug", "capturedAt": "2026-09-15T00:00:00Z", "content": {
            "fix": "校验注册路径仍指向当前项目。",
            "learningSignals": [{
                "title": "项目身份校验", "instruction": "校验注册路径仍指向当前项目。",
                "rationale": "项目移动后旧路径可能失效。", "stage": "PRE_CHECK",
            }],
        },
    }], skill="debug")

    assert len([rule for rule in summary["rules"] if "校验注册路径" in rule["instruction"]]) == 1
    assert summary["rules"][0]["type"] == "LEARNING_SIGNAL"


def test_specialized_summary_does_not_extract_unrecognized_arbitrary_fields():
    summary = build_summary([{
        "recordId": "record-plan", "capturedAt": "2026-09-15T00:00:00Z",
        "content": {"customerPayload": "不得被误认为训练规则"},
    }], skill="plan")

    assert summary["rules"] == []
    assert summary["statistics"]["emptySignalResults"] == 1


def test_specialized_summary_drops_single_unreviewed_task_output():
    summary = build_summary([{
        "recordId": "record-explain", "capturedAt": "2026-09-15T00:00:00Z",
        "reviewNote": "", "content": {
            "concept": "Summary rule status",
            "keyPoints": ["PENDING blocks Summary review completion"],
            "misconceptions": ["PENDING does not mean enabled"],
        },
    }], skill="explain")

    assert summary["rules"] == []
    assert summary["statistics"]["lowEvidenceClusters"] == 2


def test_specialized_summary_requires_independent_runs_for_repeated_output():
    records = [{"recordId": f"record-{index}", "runId": "same-run",
                "capturedAt": f"2026-09-15T00:00:0{index}Z", "content": {
                    "concept": "API errors", "keyPoints": ["Explain the error condition before its remedy."]}}
               for index in range(2)]
    summary = build_summary(records, skill="explain")
    assert summary["rules"] == []
    records[1]["runId"] = "other-run"
    summary = build_summary(records, skill="explain")
    assert summary["rules"][0]["supportCount"] == 2
    assert summary["rules"][0]["confidence"] == "MEDIUM"


def test_specialized_summary_does_not_flatten_verification_metadata_into_rules():
    summary = build_summary([{
        "recordId": "record-implement", "capturedAt": "2026-09-15T00:00:00Z",
        "content": {"scope": "配置保存", "verification": {
            "command": "pytest -q", "result": "42 passed",
        }},
    }], skill="implement")

    assert summary["rules"] == []
    assert summary["statistics"]["emptySignalResults"] == 1


def test_specialized_summary_keeps_all_instruction_aliases_in_nested_objects():
    summary = build_summary([{
        "recordId": "record-implement", "capturedAt": "2026-09-15T00:00:00Z",
        "reviewNote": "人工确认这些指令可复用",
        "content": {"changes": [{
            "instruction": "Validate the input first.",
            "recommendation": "Preserve the original error chain.",
        }]},
    }], skill="implement")

    assert {rule["instruction"] for rule in summary["rules"]} == {
        "Validate the input first.", "Preserve the original error chain.",
    }


def test_specialized_summary_preserves_human_reviewed_plain_text():
    summary = build_summary([{
        "recordId": "record-debug-edit", "capturedAt": "2026-09-15T00:00:00Z",
        "reviewNote": "人工改写为可复用检查", "content": "先验证配置来源，再判断运行时是否缺少依赖。",
    }], skill="debug")

    assert summary["rules"][0]["instruction"] == "先验证配置来源，再判断运行时是否缺少依赖。"
    assert summary["rules"][0]["type"] == "HUMAN_REVIEWED_CANDIDATE"
    assert summary["rules"][0]["status"] == "PENDING"


def test_specialized_summary_keeps_all_matching_fields_from_one_result():
    summary = build_summary([{
        "recordId": "record-implement", "capturedAt": "2026-09-15T00:00:00Z",
        "reviewNote": "人工确认这些指令可复用",
        "content": {
            "scope": "配置保存", "decisions": ["使用临时文件完成原子替换。"],
            "changes": ["写入前递归校验配置字段。"],
            "verification": ["覆盖并发写入。"],
        },
    }], skill="implement")

    instructions = [rule["instruction"] for rule in summary["rules"]]
    assert any("原子替换" in value for value in instructions)
    assert any("递归校验" in value for value in instructions)
    assert any("并发写入" in value for value in instructions)


def test_create_and_review_summary_filters_ineligible_records(tmp_path, monkeypatch):
    project = tmp_path / "project"
    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    database.parent.mkdir(parents=True)
    connection = connect_database(database)
    project_id = "project-test"
    base = (project_id, "project", str(project), "code-review", "run", "delivery", "succeeded")
    rows = [
        ("reviewed", *base, "2026-09-01T00:00:00Z", json.dumps({"findings": [finding("并发写入没有事务保护", "检查并发写入的事务边界。")]}), "ACTIVE", 1),
        ("unreviewed", *base, "2026-09-02T00:00:00Z", json.dumps({"findings": [finding("未审核问题", "不应进入汇总。")]}), "ACTIVE", 0),
        ("excluded", *base, "2026-09-03T00:00:00Z", json.dumps({"findings": [finding("已排除问题", "不应进入汇总。")]}), "EXCLUDED", 1),
    ]
    connection.executemany(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, run_id, stage, run_status,
            captured_at, output_json, review_status, reviewed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    connection.execute(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, run_id, stage, run_status,
            captured_at, output_json, review_status, reviewed, capture_source, hook_status)
           VALUES ('hook-only', ?, 'project', ?, 'code-review', 'hook-run', 'direct.host-hook',
                   'succeeded', '2026-09-04T00:00:00Z', ?, 'ACTIVE', 1, 'HOST_HOOK', 'CAPTURED')""",
        (
            project_id, str(project),
            json.dumps({"findings": [finding(
                "Hook-only evidence must stay auxiliary",
                "This reviewed Hook result must not enter a Summary.",
            )]}),
        ),
    )
    connection.commit()
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project), "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})

    created = review_server.create_summary({"projectId": project_id, "skill": "code-review"})

    assert created["sourceCount"] == 1
    assert created["summary"]["format"] == "forge-skill-training-summary-v5"
    assert created["summary"]["status"] == "DRAFT"
    assert created["summary"]["statistics"]["eligibleRecords"] == 1
    rule = created["summary"]["rules"][0]
    reviewed = review_server.review_summary({
        "projectId": project_id, "skill": "code-review", "version": created["version"],
        "rules": [{"id": rule["id"], "stage": "PRE_CHECK", "status": "CONFIRMED",
                   "instruction": "检查并发写入是否具备明确的事务边界。"}],
    })
    assert reviewed["status"] == "REVIEWED"

    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT lifecycle_status FROM learning_summaries WHERE version = 1").fetchone()[0] == "REVIEWED"
        assert check.execute("SELECT COUNT(*) FROM learning_summary_sources").fetchone()[0] == 1

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE learning_records SET captured_at = ?, is_classic = 1, classic_reason = ? WHERE id = ?",
        ("2020-01-01T00:00:00Z", "长期保留的回归案例", "reviewed"),
    )
    connection.commit()
    connection.close()
    second = review_server.create_summary({"projectId": project_id, "skill": "code-review"})
    assert second["version"] == 2
    assert second["sourceCount"] == 1
    assert second["summary"]["window"]["classicRecords"] == 1
    deleted = review_server.delete_summary({"projectId": project_id, "skill": "code-review", "version": 2})
    assert deleted["deleted"] is True
    with closing(sqlite3.connect(database)) as check, check:
        assert check.execute("SELECT COUNT(*) FROM learning_summaries WHERE version = 2").fetchone()[0] == 0
        assert check.execute(
            "SELECT COUNT(*) FROM learning_summary_sources s "
            "LEFT JOIN learning_summaries v ON v.id = s.summary_id WHERE v.id IS NULL"
        ).fetchone()[0] == 0


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


@pytest.mark.parametrize("extra", [
    {}, {"status": "incomplete"}, {"status": "failed"}, {"status": "queued"},
    {"status": "completed", "error": {"message": "failed"}},
    {"status": "completed", "incomplete_details": {"reason": "max_output_tokens"}},
])
def test_refine_rejects_unfinished_response_without_new_version(tmp_path, monkeypatch, extra):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    payload = {"output_text": json.dumps({"rules": []}), **extra}
    monkeypatch.setattr(review_server.urllib.request, "urlopen",
                        lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(ValueError):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 1


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


def _draft_for_refinement(tmp_path, monkeypatch):
    project = tmp_path / "refine-project"
    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    database.parent.mkdir(parents=True)
    connection = connect_database(database)
    project_id = "refine-project"
    base = (project_id, "project", str(project), "code-review", "run-1", "delivery", "succeeded")
    connection.execute(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, run_id, stage, run_status,
            captured_at, output_json, review_status, reviewed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1)""",
        ("record-1", *base, "2026-09-01T00:00:00Z",
         json.dumps({"findings": [finding("并发写入没有事务保护", "检查事务边界。")]})),
    )
    connection.commit()
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project), "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    created = review_server.create_summary({"projectId": project_id, "skill": "code-review"})
    config_path = tmp_path / "llm-refiner.json"
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    monkeypatch.setattr(review_server, "_environment_value", lambda _name: "test-key")
    original_call = review_server._call_llm

    def call_with_classification(config, api_key, instruction, payload):
        if "Classify every candidate" in instruction:
            return json.dumps({"decisions": [
                {"candidateId": rule["id"], "decision": "KEEP", "reason": "Reusable check"}
                for rule in payload["candidates"]
            ]}), {}
        return original_call(config, api_key, instruction, payload)

    monkeypatch.setattr(review_server, "_call_llm", call_with_classification)
    return project_id, database, created["version"]


def test_refine_uses_responses_api_and_persists_rule_sources(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    with closing(sqlite3.connect(database)) as connection, connection:
        source_json = connection.execute(
            "SELECT summary_json FROM learning_summaries WHERE version = ?", (version,)
        ).fetchone()[0]
    candidate_id = json.loads(source_json)["rules"][0]["id"]
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    calls = []
    response_payload = {"status": "completed", "output_text": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "type": "workflow",
        "title": "检查事务边界", "instruction": "检查并发写入是否具备事务边界。",
        "rationale": "重复证据", "status": "PENDING", "supportCount": 1,
        "candidateIds": [candidate_id], "trigger": "When reviewing concurrent writes",
        "verification": "Confirm transactions protect the write path",
        "sourceRecordIds": ["record-1"], "confidence": "High",
    }]}, ensure_ascii=False)}

    def fake_urlopen(request, timeout):
        calls.append((request, timeout, json.loads(request.data.decode("utf-8"))))
        return _FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(review_server.urllib.request, "urlopen", fake_urlopen)
    refined = review_server.refine_summary({
        "projectId": project_id, "skill": "code-review", "version": version,
        "language": "en",
    })
    assert calls[0][2]["input"]
    assert "messages" not in calls[0][2]
    assert "temperature" not in calls[0][2]
    assert "stream" not in calls[0][2]
    request_text = json.dumps(calls[0][2], ensure_ascii=False)
    assert "Simplified Chinese" not in request_text
    assert "English" in request_text
    assert refined["sourceVersion"] == version
    assert refined["version"] == version + 1
    assert refined["summary"]["version"] == version + 1
    assert refined["summary"]["refinement"]["mode"] == "explicit_llm"
    assert refined["summary"]["refinement"]["outputLanguage"] == "en"
    assert refined["summary"]["rules"][0]["confidence"] == "LOW"
    assert refined["summary"]["candidateDecisions"][0]["decision"] == "KEEP"
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute(
            "SELECT summary_json FROM learning_summaries WHERE version = ?", (version,)
        ).fetchone()[0] == source_json
        assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 2
        assert connection.execute("SELECT rule_id, record_id FROM learning_summary_rule_sources").fetchall() == [("rule-1", "record-1")]


def test_refine_rejects_unsupported_output_language():
    with pytest.raises(ValueError, match="language must be zh-CN or en"):
        review_server.refine_summary({
            "projectId": "project", "skill": "code-review", "version": 1,
            "language": "fr",
        })


def test_learning_pages_share_language_asset_and_refinement_contract():
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
    assert "language:window.ForgeI18n?.language||'zh-CN'" in versions_html
    assert '<option value="PRE_CHECK"' in versions_html
    assert '<option value="FINAL_VALIDATION"' in versions_html
    assert '<option value="PENDING"' in versions_html
    assert '<option value="CONFIRMED"' in versions_html
    assert '<option value="EXCLUDED"' in versions_html
    assert "'执行前检查':'Pre-check'" in versions_html
    assert "'待审核':'Pending'" in versions_html
    assert 'data-overlay-select' in versions_html
    assert "modern&&state==='REVIEWED'" in versions_html
    assert "tag?.textContent==='REVIEWED'" not in versions_html
    assert 'class="danger" data-delete' in versions_html
    assert "[data-delete]" in versions_html
    assert "if(!selected.length)" in versions_html
    assert "overlayButton.disabled=selected===0" in versions_html
    assert "language=window.ForgeI18n?.language||'en'" in versions_html
    assert "'Skill 汇总管理':'Skill Summary Management'" in versions_html
    assert 'href="/overlays"' in review_html
    assert 'href="/overlays"' in versions_html
    assert 'id="overlays"' not in versions_html
    assert 'id="overlays"' in overlays_html
    assert 'href="/versions"' in overlays_html
    assert "'/api/review-overlay'" in overlays_html
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


def test_refine_rejects_source_changed_while_llm_is_running(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    with closing(sqlite3.connect(database)) as connection, connection:
        candidate_id = json.loads(connection.execute("SELECT summary_json FROM learning_summaries WHERE version = ?", (version,)).fetchone()[0])["rules"][0]["id"]
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    response_payload = {"status": "completed", "output_text": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "type": "workflow", "title": "事务边界",
        "rationale": "重复证据", "confidence": "High", "status": "PENDING",
        "instruction": "检查事务边界。", "sourceRecordIds": ["record-1"],
        "candidateIds": [candidate_id], "trigger": "当审查并发写入时",
        "verification": "确认事务边界覆盖写入路径",
    }]})}

    def change_source_then_respond(*_args, **_kwargs):
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                "UPDATE learning_summaries SET lifecycle_status = 'ARCHIVED' WHERE version = ?", (version,)
            )
        return _FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(review_server.urllib.request, "urlopen", change_source_then_respond)
    with pytest.raises(ValueError, match="source summary changed"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 1
        assert connection.execute(
            "SELECT lifecycle_status FROM learning_summaries WHERE version = ?", (version,)
        ).fetchone()[0] == "ARCHIVED"


def test_refine_rejects_incomplete_rule_metadata(tmp_path, monkeypatch):
    project_id, _database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    response_payload = {"status": "completed", "output_text": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "status": "PENDING",
        "instruction": "检查事务边界。", "sourceRecordIds": ["record-1"],
    }]})}
    monkeypatch.setattr(
        review_server.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(json.dumps(response_payload).encode("utf-8")),
    )
    with pytest.raises(ValueError, match="rule type"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


def test_refine_can_discard_all_non_reusable_candidates(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "baseUrl": "https://example.test/v1",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    response_payload = {"status": "completed", "output_text": json.dumps({"rules": []})}
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(json.dumps(response_payload).encode("utf-8")),
    )

    refined = review_server.refine_summary({
        "projectId": project_id, "skill": "code-review", "version": version,
    })

    assert refined["summary"]["rules"] == []
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 2


def test_refinement_labels_cover_specialized_skills_and_known_failure():
    cases = json.loads((REPOSITORY_ROOT / "forge" / "evals" / "summary-refinement-cases.json").read_text(encoding="utf-8"))
    assert {"KEEP", "DISCARD", "CONFLICT"} <= {case["expectedDecision"] for case in cases["cases"]}
    assert {case["skill"] for case in cases["cases"]} <= set(SKILL_CRITERIA)
    assert any(case["id"] == "explain-ui-state" and case["expectedDecision"] == "DISCARD" for case in cases["cases"])


def test_refine_discarded_candidate_never_reaches_synthesis(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({"enabled": True, "baseUrl": "https://example.test/v1",
                                   "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY"})
    calls = []

    def classify(_config, _key, instruction, payload):
        calls.append(payload)
        assert "Classify every candidate" in instruction
        assert payload["records"][0]["recordId"] == "record-1"
        return json.dumps({"decisions": [{"candidateId": item["id"], "decision": "DISCARD",
                                         "reason": "One-off finding"} for item in payload["candidates"]]}), {}

    monkeypatch.setattr(review_server, "_call_llm", classify)
    refined = review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})
    assert len(calls) == 1
    assert refined["summary"]["rules"] == []
    assert refined["summary"]["candidateDecisions"][0]["sourceRecordIds"] == ["record-1"]
    assert len(review_server.summary_evidence({"project": [project_id], "skill": ["code-review"],
                                                "version": [str(version + 1)]})["records"]) == 1
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_summary_rule_sources").fetchone()[0] == 0


def test_refinement_rejects_missing_and_duplicated_candidate_decisions():
    candidates = [{"id": "one"}, {"id": "two"}]
    for decisions in ([{"candidateId": "one", "decision": "KEEP", "reason": "Useful"}],
                      [{"candidateId": "one", "decision": "KEEP", "reason": "Useful"}] * 2):
        with pytest.raises(ValueError, match="every candidate exactly once"):
            validate_decisions({"decisions": decisions}, candidates)


def test_refinement_rejects_unapproved_citations_and_computes_confidence():
    candidates = [{"id": "candidate", "sourceRecordIds": ["record-1"]}]
    records = [{"recordId": "record-1", "runId": "run-1", "reviewNote": ""}]
    rule = {"id": "rule-1", "candidateIds": ["candidate"], "sourceRecordIds": ["record-1"],
            "stage": "PRE_CHECK", "status": "PENDING", "type": "workflow", "title": "Check transaction",
            "trigger": "When reviewing concurrent writes", "instruction": "Verify the transaction boundary.",
            "verification": "Confirm writes use the same transaction.", "rationale": "Evidence", "confidence": "HIGH"}
    with pytest.raises(ValueError, match="unapproved candidate IDs"):
        validate_rules({"rules": [rule]}, [], candidates, records)
    with pytest.raises(ValueError, match="source IDs"):
        validate_rules({"rules": [{**rule, "sourceRecordIds": ["unrelated"]}]},
                       [{"candidateId": "candidate"}], candidates, records)
    assert validate_rules({"rules": [rule]}, [{"candidateId": "candidate"}], candidates, records)[0]["confidence"] == "LOW"


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


def test_refine_rejects_damaged_unicode_text(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "baseUrl": "https://example.test/v1",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    response_payload = {"status": "completed", "output_text": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "type": "workflow",
        "title": "damaged \ufffd text", "rationale": "evidence", "confidence": "LOW",
        "status": "PENDING", "instruction": "check input", "sourceRecordIds": ["record-1"],
    }]})}
    monkeypatch.setattr(
        review_server.urllib.request, "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(json.dumps(response_payload).encode("utf-8")),
    )

    with pytest.raises(ValueError, match="damaged Unicode"):
        review_server.refine_summary({
            "projectId": project_id, "skill": "code-review", "version": version,
        })
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 1


def test_refine_uses_chat_completions_and_rejects_empty_sources(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    with closing(sqlite3.connect(database)) as connection, connection:
        candidate_id = json.loads(connection.execute("SELECT summary_json FROM learning_summaries WHERE version = ?", (version,)).fetchone()[0])["rules"][0]["id"]
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/chat/completions",
        "model": "test-model", "wireApi": "chat_completions", "apiKeyEnv": "TEST_KEY",
    })
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "type": "workflow", "title": "事务边界",
        "rationale": "重复证据", "confidence": "High", "status": "PENDING",
        "instruction": "检查事务边界。", "sourceRecordIds": [],
        "candidateIds": [candidate_id], "trigger": "当审查并发写入时", "verification": "检查事务边界",
    }]})}}]}
    monkeypatch.setattr(review_server.urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="source IDs"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


def test_refine_rejects_oversized_response_before_parsing(tmp_path, monkeypatch):
    project_id, _database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    oversized = b"{" + b"x" * (review_server.MAX_LLM_RESPONSE_BYTES + 1)
    monkeypatch.setattr(review_server.urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeResponse(oversized))
    with pytest.raises(ValueError, match="256 KB"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


@pytest.mark.parametrize(
    ("wire_api", "response_payload", "message"),
    [
        ("responses", {"output": [None]}, "Responses output"),
        ("responses", {"output": [{"content": [None]}]}, "Responses content"),
        ("chat_completions", {"choices": []}, "Chat Completions choices"),
        ("chat_completions", {"choices": [{"message": []}]}, "Chat Completions message"),
    ],
)
def test_refine_rejects_malformed_llm_response_shapes(
    tmp_path, monkeypatch, wire_api, response_payload, message
):
    project_id, _database, version = _draft_for_refinement(tmp_path, monkeypatch)
    endpoint = "https://example.test/v1/responses" if wire_api == "responses" else "https://example.test/v1/chat/completions"
    review_server.save_llm_config({
        "enabled": True, "endpoint": endpoint, "model": "test-model",
        "wireApi": wire_api, "apiKeyEnv": "TEST_KEY",
    })
    monkeypatch.setattr(
        review_server.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(json.dumps(response_payload).encode("utf-8")),
    )

    with pytest.raises(ValueError, match=message):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


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

    with pytest.raises(ValueError) as captured:
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

    with pytest.raises(ValueError, match="timed out after 60 seconds"):
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

    with pytest.raises(ValueError) as captured:
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

    with pytest.raises(ValueError) as captured:
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

    with pytest.raises(ValueError, match="exceeded 180 seconds"):
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
    with pytest.raises(ValueError, match="JSON object"):
        review_server.refine_summary([])


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
