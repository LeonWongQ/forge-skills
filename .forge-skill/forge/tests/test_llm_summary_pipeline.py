from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "skills" / "learning-collector" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from forge_cli.learning_collector import DATABASE_SCHEMA_VERSION, connect_database
from llm_summary_pipeline import (
    LlmProviderError,
    LlmTimeoutError,
    LlmTransportError,
    SUMMARY_FORMAT,
    _safe_error_code,
    create_summary_generation_job,
    estimate_summary_generation,
    generate_llm_summary,
    run_summary_generation_job,
)
import summary_generation_service as summary_service
import llm_summary_pipeline as summary_pipeline
from summary_generation_service import (
    interrupt_stale_jobs,
    run_summary_submission,
    retry_summary_job,
    start_summary_job,
    summary_job_status,
)


def _records(database: Path, count: int, *, project_id: str = "project-ai", skill: str = "plan") -> None:
    connection = connect_database(database)
    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with connection:
        connection.executemany(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, run_id, captured_at,
                output_json, reviewed, review_status, capture_source)
               VALUES (?, ?, 'project', ?, ?, ?, ?, ?, 1, 'ACTIVE', 'SKILL_CONTRACT')""",
            [
                (
                    f"record-{index}", project_id, str(database.parent), skill, f"run-{index}",
                    captured_at,
                    json.dumps({"objective": f"Plan {index}", "detail": "x" * 500}),
                )
                for index in range(count)
            ],
        )
    connection.close()


def _candidate(source_ids: list[str], candidate_ids: list[str] | None = None) -> dict:
    value = {
        "id": "model-candidate",
        "sourceRecordIds": source_ids,
        "stage": "PRE_CHECK",
        "type": "PLAN_ADJUSTMENT",
        "title": "Validate dependencies",
        "trigger": "When a plan crosses component boundaries",
        "instruction": "Identify dependencies before sequencing implementation phases.",
        "verification": "Verify every phase names its prerequisites.",
        "antiPattern": "Do not sequence work before identifying prerequisites.",
        "rationale": "Unstated dependencies make otherwise valid plans fail during execution.",
    }
    if candidate_ids is not None:
        value["candidateIds"] = candidate_ids
    return value


class SuccessfulLlm:
    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, instruction: str, payload: object) -> tuple[str, dict]:
        assert isinstance(payload, dict)
        usage = {"status": "reported", "inputTokens": 10, "outputTokens": 5, "totalTokens": 15}
        if "records" in payload:
            self.calls.append("MAP")
            ids = [record["recordId"] for record in payload["records"]]
            return json.dumps({
                "recordDecisions": [
                    {"recordId": record_id, "decision": "KEEP", "reason": "Reusable planning evidence."}
                    for record_id in ids
                ],
                "candidates": [_candidate([record_id]) for record_id in ids],
            }), usage
        candidate_ids = [candidate["id"] for candidate in payload["candidates"]]
        source_ids = list(dict.fromkeys(
            source for candidate in payload["candidates"] for source in candidate["sourceRecordIds"]
        ))
        decisions = [
            {"candidateId": candidate_id, "decision": "KEEP", "reason": "Supported reusable guidance."}
            for candidate_id in candidate_ids
        ]
        if "consolidating" in instruction:
            self.calls.append("REDUCE")
            return json.dumps({
                "decisions": decisions,
                "candidates": [_candidate(source_ids, candidate_ids)],
            }), usage
        self.calls.append("FINAL")
        return json.dumps({
            "decisions": decisions,
            "rules": [_candidate(source_ids, candidate_ids)],
        }), usage


def _wait_for_status(database: Path, job_id: str, statuses: set[str], timeout: float = 3) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = summary_job_status(database, job_id=job_id)
        if status and status["status"] in statuses:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {statuses}")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LlmTimeoutError("timeout"), "LLM_TIMEOUT"),
        (LlmTransportError("network"), "LLM_TRANSPORT_ERROR"),
        (LlmProviderError("HTTP 503"), "LLM_PROVIDER_ERROR"),
        (ValueError("bad JSON"), "INVALID_GENERATION_RESULT"),
    ],
)
def test_generation_error_codes_preserve_failure_category(error, code):
    assert _safe_error_code(error) == code


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LlmTimeoutError("timeout"), "LLM_TIMEOUT"),
        (LlmTransportError("network"), "LLM_TRANSPORT_ERROR"),
        (LlmProviderError("HTTP 503"), "LLM_PROVIDER_ERROR"),
        (ValueError("invalid output"), "INVALID_GENERATION_RESULT"),
    ],
)
def test_generation_persists_typed_llm_failure(error, code, tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)

    def fail(_instruction, _payload):
        raise error

    with pytest.raises(type(error), match=str(error)):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=fail,
        )

    connection = connect_database(database)
    assert tuple(connection.execute(
        "SELECT status, error_code FROM summary_generation_jobs"
    ).fetchone()) == ("FAILED", code)
    assert tuple(connection.execute(
        "SELECT status, error_code FROM summary_generation_batches"
    ).fetchone()) == ("FAILED", code)
    connection.close()


def test_schema_adds_persisted_summary_generation_tables(tmp_path):
    database = tmp_path / "learning.sqlite"
    connection = connect_database(database)
    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    indexes = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    assert connection.execute("PRAGMA user_version").fetchone()[0] == DATABASE_SCHEMA_VERSION == 14
    assert {
        "summary_generation_jobs", "summary_generation_sources", "summary_generation_batches",
    } <= tables
    assert "idx_one_active_summary_generation" in indexes
    connection.close()


def test_schema_migrates_existing_generation_jobs_with_persisted_language(tmp_path):
    database = tmp_path / "learning.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE summary_generation_jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, skill TEXT NOT NULL,
            status TEXT NOT NULL, window_months INTEGER NOT NULL, cutoff_at TEXT NOT NULL,
            source_digest TEXT NOT NULL, skill_digest TEXT NOT NULL, model TEXT NOT NULL,
            prompt_version TEXT NOT NULL, source_count INTEGER NOT NULL,
            total_batches INTEGER NOT NULL DEFAULT 0, completed_batches INTEGER NOT NULL DEFAULT 0,
            usage_json TEXT NOT NULL DEFAULT '{}', error_code TEXT, summary_id TEXT,
            created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT
        )"""
    )
    connection.execute(
        "INSERT INTO summary_generation_jobs "
        "(id, project_id, skill, status, window_months, cutoff_at, source_digest, skill_digest, "
        "model, prompt_version, source_count, created_at) "
        "VALUES ('old-job', 'project', 'plan', 'FAILED', 6, 'now', 'source', 'skill', "
        "'model', 'prompt', 1, 'now')"
    )
    connection.execute("PRAGMA user_version=11")
    connection.commit()
    connection.close()

    migrated = connect_database(database)
    columns = {row["name"] for row in migrated.execute("PRAGMA table_info(summary_generation_jobs)")}
    assert "language" in columns
    assert "provider_identity" in columns
    assert migrated.execute(
        "SELECT language FROM summary_generation_jobs WHERE id = 'old-job'"
    ).fetchone()[0] == "zh-CN"
    assert migrated.execute(
        "SELECT provider_identity FROM summary_generation_jobs WHERE id = 'old-job'"
    ).fetchone()[0] == ""
    assert migrated.execute("PRAGMA user_version").fetchone()[0] == DATABASE_SCHEMA_VERSION
    migrated.close()


def test_llm_summary_pipeline_batches_reduces_commits_and_reuses_cache(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 5)
    first_llm = SuccessfulLlm()

    first = generate_llm_summary(
        database, project_id="project-ai", skill="plan", skill_text="# Plan\nPlan carefully.",
        model="test-model", call_llm=first_llm, batch_bytes=2_200,
        provider_identity="test-service",
    )

    assert first["summary"]["format"] == SUMMARY_FORMAT
    assert first["summary"]["coverage"]["sourceRecords"] == 5
    assert first["summary"]["coverage"]["processedRecords"] == 5
    assert first["summary"]["coverage"]["coverageRate"] == 1.0
    assert first["summary"]["coverage"]["finalRules"] == 1
    assert first_llm.calls.count("MAP") >= 2
    assert "REDUCE" in first_llm.calls
    assert first_llm.calls[-1] == "FINAL"

    connection = connect_database(database)
    job = connection.execute(
        "SELECT status, completed_batches, total_batches, summary_id "
        "FROM summary_generation_jobs WHERE id = ?", (first["jobId"],)
    ).fetchone()
    assert tuple(job[:3]) == ("SUCCEEDED", len(first_llm.calls), len(first_llm.calls))
    assert job["summary_id"] == first["summaryId"]
    assert connection.execute(
        "SELECT COUNT(*) FROM learning_summary_sources WHERE summary_id = ?", (first["summaryId"],)
    ).fetchone()[0] == 5
    assert connection.execute(
        "SELECT COUNT(*) FROM learning_summary_rule_sources WHERE summary_id = ?", (first["summaryId"],)
    ).fetchone()[0] == 5
    connection.close()

    second_llm = SuccessfulLlm()
    second = generate_llm_summary(
        database, project_id="project-ai", skill="plan", skill_text="# Plan\nPlan carefully.",
        model="test-model", call_llm=second_llm, batch_bytes=2_200,
        provider_identity="test-service",
    )
    assert second["version"] == first["version"] + 1
    assert second_llm.calls == []
    assert second["summary"]["generation"]["usage"]["cachedCalls"] > 0


@pytest.mark.parametrize("first_provider,second_provider", [
    ("service-a:responses", "service-b:responses"),
    ("service-a:responses", "service-a:chat_completions"),
    ("", ""),
])
def test_summary_cache_does_not_cross_services_or_unknown_identity(
    tmp_path, first_provider, second_provider,
):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    arguments = dict(project_id="project-ai", skill="plan", skill_text="# Plan", model="same-alias")
    first = generate_llm_summary(
        database, call_llm=SuccessfulLlm(), provider_identity=first_provider, **arguments,
    )
    new_service = SuccessfulLlm()
    second = generate_llm_summary(
        database, call_llm=new_service, provider_identity=second_provider, **arguments,
    )
    assert new_service.calls == ["MAP", "FINAL"]
    assert second["summary"]["generation"]["usage"]["cachedCalls"] == 0
    assert second["summary"]["generation"]["providerIdentity"] == second_provider
    connection = connect_database(database)
    assert connection.execute(
        "SELECT provider_identity FROM summary_generation_jobs WHERE id = ?", (first["jobId"],),
    ).fetchone()[0] == first_provider
    connection.close()


def test_final_packet_budget_includes_skill_criteria_and_language(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    criteria = "C" * 300
    monkeypatch.setitem(summary_pipeline.SKILL_CRITERIA, "plan", criteria)
    large_candidates = []
    for index in range(summary_pipeline.FINAL_CANDIDATE_LIMIT):
        candidate = _candidate(["record-0"])
        candidate.update({
            "title": f"Rule {index:02} " + "T" * 90,
            "trigger": "G" * 200,
            "instruction": "I" * 500,
            "verification": "V" * 300,
            "antiPattern": "A" * 300,
            "rationale": "R" * 300,
        })
        large_candidates.append(candidate)

    compact = {"skill": "plan", "candidates": [
        {**candidate, "id": f"candidate-map-placeholder-{index:03}"}
        for index, candidate in enumerate(large_candidates, 1)
    ]}
    complete = {
        "skill": "plan", "skillCriteria": criteria, "outputLanguage": "zh-CN",
        "candidates": compact["candidates"],
    }
    compact_bytes = summary_pipeline._bytes(compact)
    complete_bytes = summary_pipeline._bytes(complete)
    batch_bytes = compact_bytes + (complete_bytes - compact_bytes) // 2
    assert compact_bytes < batch_bytes < complete_bytes
    calls = []

    def boundary_llm(instruction, payload):
        assert summary_pipeline._bytes(payload) <= batch_bytes
        usage = {"status": "reported", "inputTokens": 1, "outputTokens": 1, "totalTokens": 2}
        if "records" in payload:
            calls.append("MAP")
            return json.dumps({
                "recordDecisions": [{
                    "recordId": "record-0", "decision": "KEEP", "reason": "Reusable evidence.",
                }],
                "candidates": large_candidates,
            }), usage
        candidate_ids = [candidate["id"] for candidate in payload["candidates"]]
        decisions = [
            {"candidateId": candidate_id, "decision": "KEEP", "reason": "Reusable guidance."}
            for candidate_id in candidate_ids
        ]
        source_ids = list(dict.fromkeys(
            source for candidate in payload["candidates"] for source in candidate["sourceRecordIds"]
        ))
        merged = _candidate(source_ids, candidate_ids)
        if "consolidating" in instruction:
            calls.append("REDUCE")
            return json.dumps({"decisions": decisions, "candidates": [merged]}), usage
        calls.append("FINAL")
        return json.dumps({"decisions": decisions, "rules": [merged]}), usage

    result = generate_llm_summary(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=boundary_llm, batch_bytes=batch_bytes,
    )

    assert result["summary"]["coverage"]["finalRules"] == 1
    assert "REDUCE" in calls
    assert calls[-1] == "FINAL"


def test_llm_summary_pipeline_allows_complete_no_learning_result(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 2)

    def no_learning(_instruction, payload):
        return json.dumps({
            "recordDecisions": [
                {"recordId": record["recordId"], "decision": "NO_LEARNING", "reason": "Task-specific output."}
                for record in payload["records"]
            ],
            "candidates": [],
        }), {"status": "reported", "inputTokens": 1, "outputTokens": 1, "totalTokens": 2}

    result = generate_llm_summary(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=no_learning,
    )

    assert result["summary"]["rules"] == []
    assert result["summary"]["coverage"]["recordDecisions"]["NO_LEARNING"] == 2
    assert result["summary"]["generation"]["batchCount"] == 1


def test_conflict_evidence_is_dispositioned_without_becoming_a_rule(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)

    def conflict_only(_instruction, payload):
        return json.dumps({
            "recordDecisions": [{
                "recordId": payload["records"][0]["recordId"],
                "decision": "CONFLICT",
                "reason": "The evidence contradicts existing guidance.",
            }],
            "candidates": [],
        }), {"status": "unreported"}

    result = generate_llm_summary(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=conflict_only,
    )

    assert result["summary"]["rules"] == []
    assert result["summary"]["coverage"]["recordDecisions"]["CONFLICT"] == 1
    assert result["summary"]["coverage"]["mapCandidates"] == 0


def test_conflict_evidence_cannot_source_a_candidate(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)

    def invalid_conflict_candidate(_instruction, payload):
        record_id = payload["records"][0]["recordId"]
        return json.dumps({
            "recordDecisions": [{
                "recordId": record_id,
                "decision": "CONFLICT",
                "reason": "The evidence contradicts existing guidance.",
            }],
            "candidates": [_candidate([record_id])],
        }), {"status": "unreported"}

    with pytest.raises(ValueError, match="only kept records"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=invalid_conflict_candidate,
        )

    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0
    connection.close()


def test_generation_estimate_uses_the_same_complete_source_plan(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 3)

    estimate = estimate_summary_generation(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        batch_bytes=2_200,
    )

    assert estimate["sourceCount"] == 3
    assert estimate["evidenceBytes"] > 0
    assert estimate["estimatedMapBatches"] >= 1
    assert estimate["limits"] == {
        "maxSourceRecords": summary_pipeline.MAX_SOURCE_RECORDS,
        "maxEvidenceBytes": summary_pipeline.MAX_TOTAL_EVIDENCE_BYTES,
        "maxGenerationBatches": summary_pipeline.MAX_GENERATION_BATCHES,
    }


def test_generation_rejects_source_count_budget_before_model_calls(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 2)
    monkeypatch.setattr(summary_pipeline, "MAX_SOURCE_RECORDS", 1)
    calls = []

    with pytest.raises(ValueError, match="exceeds the 1-record source limit"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=lambda *_args: calls.append(True),
        )

    assert calls == []
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 0
    connection.close()


def test_generation_rejects_total_evidence_budget_before_model_calls(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 2)
    monkeypatch.setattr(summary_pipeline, "MAX_TOTAL_EVIDENCE_BYTES", 1)
    calls = []

    with pytest.raises(ValueError, match="evidence bytes; maximum is 1"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=lambda *_args: calls.append(True),
        )

    assert calls == []


def test_generation_rejects_map_batch_budget_before_model_calls(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    monkeypatch.setattr(summary_pipeline, "MAX_GENERATION_BATCHES", 1)
    calls = []

    with pytest.raises(ValueError, match="1 MAP batches plus final processing"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=lambda *_args: calls.append(True),
        )

    assert calls == []
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 0
    connection.close()


def test_dynamic_reduction_cannot_exceed_whole_job_batch_budget(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 2)
    monkeypatch.setattr(summary_pipeline, "FINAL_CANDIDATE_LIMIT", 1)
    monkeypatch.setattr(summary_pipeline, "MAX_GENERATION_BATCHES", 2)
    llm = SuccessfulLlm()

    with pytest.raises(ValueError, match="2-batch job limit"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=llm,
        )

    assert llm.calls == ["MAP", "REDUCE"]
    connection = connect_database(database)
    assert connection.execute(
        "SELECT status FROM summary_generation_jobs"
    ).fetchone()[0] == "FAILED"
    assert connection.execute(
        "SELECT COUNT(*) FROM summary_generation_batches"
    ).fetchone()[0] == 2
    connection.close()


def test_llm_summary_pipeline_rejects_missing_record_decision_without_summary(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 2)

    def incomplete(_instruction, payload):
        record = payload["records"][0]
        return json.dumps({
            "recordDecisions": [
                {"recordId": record["recordId"], "decision": "KEEP", "reason": "Only one decision."}
            ],
            "candidates": [_candidate([record["recordId"]])],
        }), {"status": "unreported"}

    with pytest.raises(ValueError, match="decide every input"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=incomplete,
        )

    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0
    assert connection.execute(
        "SELECT status FROM summary_generation_jobs"
    ).fetchone()[0] == "FAILED"
    assert connection.execute(
        "SELECT status FROM summary_generation_batches"
    ).fetchone()[0] == "FAILED"
    connection.close()


def test_llm_summary_pipeline_rejects_evidence_changed_during_generation(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    successful = SuccessfulLlm()
    changed = False

    def mutating_llm(instruction, payload):
        nonlocal changed
        result = successful(instruction, payload)
        if not changed:
            changed = True
            with sqlite3.connect(database) as other:
                other.execute(
                    "UPDATE learning_records SET review_note = 'changed concurrently' WHERE id = 'record-0'"
                )
        return result

    with pytest.raises(ValueError, match="source evidence changed"):
        generate_llm_summary(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=mutating_llm,
        )

    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0
    assert connection.execute("SELECT status FROM summary_generation_jobs").fetchone()[0] == "FAILED"
    connection.close()


def test_background_job_returns_before_model_completion_and_prevents_duplicate_active_job(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    entered = threading.Event()
    release = threading.Event()
    successful = SuccessfulLlm()

    def blocking_llm(instruction, payload):
        entered.set()
        assert release.wait(3)
        return successful(instruction, payload)

    job = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=blocking_llm,
    )
    assert entered.wait(1)
    assert job["status"] in {"PENDING", "RUNNING"}
    with pytest.raises(ValueError, match="already active"):
        create_summary_generation_job(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model",
        )
    release.set()
    terminal = _wait_for_status(database, job["jobId"], {"SUCCEEDED"})
    assert terminal["version"] == 1
    assert terminal["summaryId"]
    assert terminal["completedBatches"] == terminal["totalBatches"] == 2


def test_duplicate_runner_cannot_fail_the_worker_that_claimed_the_job(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    entered = threading.Event()
    release = threading.Event()
    successful = SuccessfulLlm()

    def blocking_llm(instruction, payload):
        entered.set()
        assert release.wait(3)
        return successful(instruction, payload)

    job = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=blocking_llm,
    )
    assert entered.wait(1)
    with pytest.raises(ValueError, match="not pending"):
        run_summary_generation_job(
            database, job_id=job["jobId"], skill_text="# Plan",
            call_llm=SuccessfulLlm(),
        )
    assert summary_job_status(database, job_id=job["jobId"])["status"] == "RUNNING"
    release.set()
    assert _wait_for_status(database, job["jobId"], {"SUCCEEDED"})["status"] == "SUCCEEDED"


def test_background_job_exposes_persisted_progress_without_automatic_retry(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    final_entered = threading.Event()
    final_release = threading.Event()
    successful = SuccessfulLlm()
    calls = []

    def block_final(instruction, payload):
        phase = "MAP" if "records" in payload else "FINAL"
        calls.append(phase)
        if phase == "FINAL":
            final_entered.set()
            assert final_release.wait(3)
        return successful(instruction, payload)

    job = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=block_final,
    )
    assert final_entered.wait(1)
    running = summary_job_status(database, job_id=job["jobId"])
    assert running["status"] == "RUNNING"
    assert running["completedBatches"] == 1
    assert running["totalBatches"] == 2
    final_release.set()
    _wait_for_status(database, job["jobId"], {"SUCCEEDED"})
    assert calls == ["MAP", "FINAL"]


@pytest.mark.parametrize("retry_provider,expected_calls", [
    ("test-service", ["FINAL"]),
    ("other-service", ["MAP", "FINAL"]),
])
def test_failed_job_requires_explicit_retry_and_reuses_successful_batches(
    tmp_path, retry_provider, expected_calls,
):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    successful = SuccessfulLlm()
    first_calls = []

    def fail_final(instruction, payload):
        phase = "MAP" if "records" in payload else "FINAL"
        first_calls.append(phase)
        if phase == "FINAL":
            raise RuntimeError("provider failed")
        return successful(instruction, payload)

    first = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=fail_final, language="en",
        provider_identity="test-service",
    )
    failed = _wait_for_status(database, first["jobId"], {"FAILED"})
    assert failed["errorCode"] == "GENERATION_FAILED"
    assert failed["retryable"] is True
    assert first_calls == ["MAP", "FINAL"]

    second_llm = SuccessfulLlm()
    retried = retry_summary_job(
        database, previous_job_id=first["jobId"], skill_text="# Plan",
        model="test-model", call_llm=second_llm, provider_identity=retry_provider,
    )
    succeeded = _wait_for_status(database, retried["jobId"], {"SUCCEEDED"})
    assert succeeded["jobId"] != first["jobId"]
    assert succeeded["language"] == "en"
    assert second_llm.calls == expected_calls


def test_startup_recovery_marks_pending_and_running_jobs_interrupted(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    pending = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model",
    )
    assert interrupt_stale_jobs(database) == 1
    status = summary_job_status(database, job_id=pending["jobId"])
    assert status["status"] == "INTERRUPTED"
    assert status["errorCode"] == "SERVICE_RESTARTED"
    assert status["retryable"] is True


def test_interrupted_running_job_cannot_commit_a_summary(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    entered = threading.Event()
    release = threading.Event()
    successful = SuccessfulLlm()

    def blocking_llm(instruction, payload):
        entered.set()
        assert release.wait(3)
        return successful(instruction, payload)

    job = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=blocking_llm,
    )
    assert entered.wait(1)
    assert interrupt_stale_jobs(database) == 1
    release.set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        connection = connect_database(database)
        completed = connection.execute(
            "SELECT COUNT(*) FROM summary_generation_batches "
            "WHERE job_id = ? AND status = 'SUCCEEDED'", (job["jobId"],),
        ).fetchone()[0]
        connection.close()
        if completed == 2:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("interrupted worker did not reach the commit guard")
    status = summary_job_status(database, job_id=job["jobId"])
    assert status["status"] == "INTERRUPTED"
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM learning_summaries").fetchone()[0] == 0
    connection.close()


def test_worker_start_failure_does_not_leave_an_active_job(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    monkeypatch.setattr(
        summary_service.threading.Thread, "start",
        lambda _self: (_ for _ in ()).throw(RuntimeError("thread unavailable")),
    )

    with pytest.raises(RuntimeError, match="thread unavailable"):
        start_summary_job(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", call_llm=SuccessfulLlm(),
        )

    status = summary_job_status(database, project_id="project-ai", skill="plan")
    assert status["status"] == "INTERRUPTED"
    assert status["errorCode"] == "WORKER_START_FAILED"


def test_background_worker_failure_before_pipeline_error_boundary_is_retryable(
        tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    job = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model",
    )
    monkeypatch.setattr(
        summary_service, "run_summary_generation_job",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("worker setup failed")),
    )

    summary_service._run_in_background(
        database, job_id=job["jobId"], skill_text="# Plan",
        call_llm=SuccessfulLlm(),
    )

    status = summary_job_status(database, job_id=job["jobId"])
    assert status["status"] == "FAILED"
    assert status["errorCode"] == "WORKER_FAILED"
    assert status["retryable"] is True


def test_background_worker_failure_is_reconciled_after_database_recovers(
        tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    job = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model",
    )
    monkeypatch.setattr(
        summary_service, "run_summary_generation_job",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("worker setup failed")),
    )
    real_connect = summary_service.connect_database
    connection_attempts = 0

    def unavailable_once(path, timeout=30):
        nonlocal connection_attempts
        connection_attempts += 1
        if connection_attempts == 1:
            raise sqlite3.OperationalError("database temporarily unavailable")
        return real_connect(path, timeout=timeout)

    monkeypatch.setattr(summary_service, "connect_database", unavailable_once)
    summary_service._run_in_background(
        database, job_id=job["jobId"], skill_text="# Plan",
        call_llm=SuccessfulLlm(),
    )

    connection = connect_database(database)
    assert connection.execute(
        "SELECT status FROM summary_generation_jobs WHERE id = ?", (job["jobId"],),
    ).fetchone()[0] == "PENDING"
    connection.close()

    status = summary_job_status(database, job_id=job["jobId"])
    assert status["status"] == "FAILED"
    assert status["errorCode"] == "WORKER_FAILED"
    assert status["retryable"] is True


def test_new_job_reconciles_worker_failure_before_enforcing_active_job_limit(
        tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    failed_job = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model",
    )
    monkeypatch.setattr(
        summary_service, "run_summary_generation_job",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("worker setup failed")),
    )
    real_connect = summary_service.connect_database
    connection_attempts = 0

    def unavailable_once(path, timeout=30):
        nonlocal connection_attempts
        connection_attempts += 1
        if connection_attempts == 1:
            raise sqlite3.OperationalError("database temporarily unavailable")
        return real_connect(path, timeout=timeout)

    monkeypatch.setattr(summary_service, "connect_database", unavailable_once)
    summary_service._run_in_background(
        database, job_id=failed_job["jobId"], skill_text="# Plan",
        call_llm=SuccessfulLlm(),
    )
    monkeypatch.setattr(summary_service.threading.Thread, "start", lambda _self: None)

    new_job = start_summary_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan",
        model="test-model", call_llm=SuccessfulLlm(),
    )

    assert new_job["jobId"] != failed_job["jobId"]
    connection = connect_database(database)
    assert tuple(connection.execute(
        "SELECT status, error_code FROM summary_generation_jobs WHERE id = ?",
        (failed_job["jobId"],),
    ).fetchone()) == ("FAILED", "WORKER_FAILED")
    connection.close()


def test_submission_receipt_precedes_preparation_and_duplicate_request_creates_one_job(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    entered, release = threading.Event(), threading.Event()
    original = summary_pipeline._source_plan
    results, errors, calls = [], [], []
    request = {"action": "GENERATE", "language": "en"}

    def delayed_plan(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(summary_pipeline, "_source_plan", delayed_plan)

    def create():
        calls.append("create")
        return create_summary_generation_job(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", submission_id="submission-one", language="en",
        )

    def submit():
        try:
            results.append(run_summary_submission(
                database, submission_id="submission-one", project_id="project-ai",
                skill="plan", request=request, create=create,
            ))
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=submit)
    worker.start()
    try:
        assert entered.wait(3)
        receipt = summary_job_status(database, submission_id="submission-one")
        assert receipt["status"] == "PREPARING" and receipt["jobId"] is None
        assert summary_job_status(database, project_id="project-ai", skill="plan")["status"] == "PREPARING"
        duplicate = run_summary_submission(
            database, submission_id="submission-one", project_id="project-ai",
            skill="plan", request=request, create=create,
        )
        assert duplicate["status"] == "PREPARING"
        with pytest.raises(ValueError, match="different request"):
            run_summary_submission(database, submission_id="submission-one", project_id="project-ai",
                                   skill="plan", request={"action": "RETRY"}, create=create)
        with pytest.raises(ValueError, match="already preparing"):
            run_summary_submission(database, submission_id="submission-two", project_id="project-ai",
                                   skill="plan", request=request, create=create)
    finally:
        release.set()
        worker.join(4)
    assert not worker.is_alive() and not errors
    after = run_summary_submission(
        database, submission_id="submission-one", project_id="project-ai",
        skill="plan", request=request, create=create,
    )
    assert after["jobId"] == results[0]["jobId"]
    assert after["status"] == "PENDING" and after["submissionId"] == "submission-one"
    assert calls == ["create"]
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 1
    connection.close()


def test_submission_failure_is_terminal_and_does_not_repeat_preparation(tmp_path):
    database = tmp_path / "learning.sqlite"
    calls = []

    def fail():
        calls.append("prepare")
        raise ValueError("no eligible records")

    args = dict(submission_id="failed-submission", project_id="project-ai", skill="plan",
                request={"action": "GENERATE"}, create=fail)
    with pytest.raises(ValueError, match="no eligible records"):
        run_summary_submission(database, **args)
    receipt = run_summary_submission(database, **args)
    assert receipt["status"] == "FAILED" and receipt["retryable"] is False
    assert receipt["errorCode"] == "INVALID_GENERATION_RESULT"
    assert calls == ["prepare"]


def test_submission_interruption_rolls_back_late_job_and_can_be_queried_after_restart(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    original = summary_pipeline._source_plan

    def interrupt_preparation(*args, **kwargs):
        assert summary_job_status(database, submission_id="interrupted")["status"] == "PREPARING"
        assert interrupt_stale_jobs(database) == 1
        return original(*args, **kwargs)

    monkeypatch.setattr(summary_pipeline, "_source_plan", interrupt_preparation)
    with pytest.raises(ValueError, match="no longer preparing"):
        run_summary_submission(
            database, submission_id="interrupted", project_id="project-ai", skill="plan",
            request={"action": "GENERATE"}, create=lambda: create_summary_generation_job(
                database, project_id="project-ai", skill="plan", skill_text="# Plan",
                model="test-model", submission_id="interrupted",
            ),
        )
    receipt = summary_job_status(database, submission_id="interrupted")
    assert receipt["status"] == "INTERRUPTED" and receipt["errorCode"] == "SERVICE_RESTARTED"
    connection = connect_database(database)
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_jobs").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_sources").fetchone()[0] == 0
    connection.close()


def test_submission_retry_links_new_job_instead_of_previous_failure(tmp_path, monkeypatch):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    previous = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan", model="test-model",
    )
    assert interrupt_stale_jobs(database) == 1
    monkeypatch.setattr(summary_service.threading.Thread, "start", lambda _self: None)
    receipt = run_summary_submission(
        database, submission_id="retry-submission", project_id="project-ai", skill="plan",
        request={"action": "RETRY", "jobId": previous["jobId"]},
        create=lambda: retry_summary_job(
            database, previous_job_id=previous["jobId"], skill_text="# Plan", model="test-model",
            call_llm=SuccessfulLlm(), submission_id="retry-submission",
        ),
    )
    status = summary_job_status(database, submission_id="retry-submission")
    assert receipt["jobId"] == status["jobId"] != previous["jobId"]
    assert status["status"] == "PENDING"


def test_submission_receipt_retains_terminal_result_after_job_is_deleted(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    run_summary_submission(
        database, submission_id="deleted-job", project_id="project-ai", skill="plan",
        request={}, create=lambda: create_summary_generation_job(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", submission_id="deleted-job",
        ),
    )
    connection = connect_database(database)
    with connection:
        connection.execute("DELETE FROM summary_generation_jobs")
    connection.close()
    result = summary_job_status(database, submission_id="deleted-job")
    assert result["status"] == "INTERRUPTED" and result["errorCode"] == "SUMMARY_JOB_DELETED"


def test_schema_13_migrates_submission_table_without_changing_existing_jobs(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    job = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan", model="test-model",
    )
    connection = connect_database(database)
    with connection:
        connection.execute("DROP TABLE summary_generation_submissions")
        connection.execute("PRAGMA user_version = 13")
    connection.close()
    assert summary_job_status(database, job_id=job["jobId"])["status"] == "PENDING"
    connection = connect_database(database)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 14
    assert connection.execute("SELECT COUNT(*) FROM summary_generation_submissions").fetchone()[0] == 0
    connection.close()


def test_new_rejected_submission_does_not_hide_an_existing_active_job(tmp_path):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    active = create_summary_generation_job(
        database, project_id="project-ai", skill="plan", skill_text="# Plan", model="test-model",
    )
    with pytest.raises(ValueError, match="already active"):
        run_summary_submission(
            database, submission_id="rejected", project_id="project-ai", skill="plan", request={},
            create=lambda: create_summary_generation_job(
                database, project_id="project-ai", skill="plan", skill_text="# Plan",
                model="test-model", submission_id="rejected",
            ),
        )
    assert summary_job_status(database, submission_id="rejected")["status"] == "FAILED"
    status = summary_job_status(database, project_id="project-ai", skill="plan")
    assert status["jobId"] == active["jobId"] and status["status"] == "PENDING"


@pytest.mark.parametrize("failure", ["connect", "write"])
@pytest.mark.parametrize("recovery", ["status", "reservation"])
def test_submission_failure_reconciles_after_database_recovers_and_preserves_original_error(
        tmp_path, monkeypatch, failure, recovery):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    real_connect = summary_service.connect_database
    attempts = 0

    class LockedTerminalWrite:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            self.connection.__enter__()
            return self

        def __exit__(self, *args):
            return self.connection.__exit__(*args)

        def executemany(self, *_args):
            raise sqlite3.OperationalError("database is locked")

        def close(self):
            self.connection.close()

    def unavailable_once(path, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            if failure == "connect":
                raise sqlite3.OperationalError("database is locked")
            return LockedTerminalWrite(real_connect(path, **kwargs))
        return real_connect(path, **kwargs)

    monkeypatch.setattr(summary_service, "connect_database", unavailable_once)
    with pytest.raises(ValueError, match="original preparation failure"):
        run_summary_submission(
            database, submission_id="failed-to-persist", project_id="project-ai", skill="plan", request={},
            create=lambda: (_ for _ in ()).throw(ValueError("original preparation failure")),
        )
    connection = connect_database(database)
    assert connection.execute("SELECT status FROM summary_generation_submissions").fetchone()[0] == "PREPARING"
    connection.close()
    if recovery == "status":
        receipt = summary_job_status(database, submission_id="failed-to-persist")
        assert receipt["status"] == "FAILED" and receipt["errorCode"] == "INVALID_GENERATION_RESULT"
    accepted = run_summary_submission(
        database, submission_id="next-request", project_id="project-ai", skill="plan", request={},
        create=lambda: create_summary_generation_job(
            database, project_id="project-ai", skill="plan", skill_text="# Plan",
            model="test-model", submission_id="next-request",
        ),
    )
    assert accepted["status"] == "PENDING"
    assert summary_job_status(database, submission_id="failed-to-persist")["status"] == "FAILED"
    assert not any(key[0] == str(database.resolve()) for key in summary_service._submission_failures)


@pytest.mark.parametrize("outcome", ["ACCEPTED", "INTERRUPTED"])
def test_submission_failure_reconciliation_preserves_committed_and_interrupted_outcomes(
        tmp_path, monkeypatch, outcome):
    database = tmp_path / "learning.sqlite"
    _records(database, 1)
    real_connect = summary_service.connect_database
    attempts = 0

    def unavailable_once(path, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise OSError("terminal write unavailable")
        return real_connect(path, **kwargs)

    monkeypatch.setattr(summary_service, "connect_database", unavailable_once)

    def finish_then_fail():
        if outcome == "ACCEPTED":
            create_summary_generation_job(
                database, project_id="project-ai", skill="plan", skill_text="# Plan",
                model="test-model", submission_id="preserved",
            )
        else:
            connection = connect_database(database)
            with connection:
                connection.execute("UPDATE summary_generation_submissions SET status='INTERRUPTED', error_code='SERVICE_RESTARTED'")
            connection.close()
        raise ValueError("late error")

    with pytest.raises(ValueError, match="late error"):
        run_summary_submission(database, submission_id="preserved", project_id="project-ai",
                               skill="plan", request={}, create=finish_then_fail)
    status = summary_job_status(database, submission_id="preserved")
    assert status["status"] == ("PENDING" if outcome == "ACCEPTED" else "INTERRUPTED")
    assert status["errorCode"] == (None if outcome == "ACCEPTED" else "SERVICE_RESTARTED")
