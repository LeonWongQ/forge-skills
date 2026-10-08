"""Background orchestration and safe status views for AI Summary generation."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from forge_cli.learning_collector import connect_database
from llm_summary_pipeline import (
    CallLlm,
    _safe_error_code,
    create_summary_generation_job,
    run_summary_generation_job,
)


RETRYABLE_STATUSES = {"FAILED", "INTERRUPTED"}
_worker_failures: set[tuple[str, str]] = set()
_worker_failures_lock = threading.Lock()
_submission_failures: dict[tuple[str, str], str] = {}
_submission_failures_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _database_key(database: Path) -> str:
    return str(database.resolve())


def _remember_worker_failure(database: Path, job_id: str) -> None:
    with _worker_failures_lock:
        _worker_failures.add((_database_key(database), job_id))


def _reconcile_worker_failures(database: Path) -> None:
    database_key = _database_key(database)
    with _worker_failures_lock:
        job_ids = [
            job_id for pending_database, job_id in _worker_failures
            if pending_database == database_key
        ]
    if not job_ids:
        return
    connection = connect_database(database, timeout=5)
    try:
        with connection:
            connection.executemany(
                "UPDATE summary_generation_jobs SET status = 'FAILED', "
                "error_code = 'WORKER_FAILED', completed_at = ? "
                "WHERE id = ? AND status IN ('PENDING', 'RUNNING')",
                [(_now(), job_id) for job_id in job_ids],
            )
    finally:
        connection.close()
    with _worker_failures_lock:
        _worker_failures.difference_update(
            (database_key, job_id) for job_id in job_ids
        )


def _safe_job(row: sqlite3.Row, version: int | None = None) -> dict:
    total = int(row["total_batches"] or 0)
    completed = int(row["completed_batches"] or 0)
    result = {
        "jobId": row["id"],
        "projectId": row["project_id"],
        "skill": row["skill"],
        "language": row["language"],
        "status": row["status"],
        "sourceCount": int(row["source_count"]),
        "completedBatches": completed,
        "totalBatches": total,
        "progress": completed / total if total else 0.0,
        "errorCode": row["error_code"],
        "summaryId": row["summary_id"],
        "version": version,
        "createdAt": row["created_at"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
        "retryable": row["status"] in RETRYABLE_STATUSES,
    }
    return result


def _reconcile_submission_failures(database: Path) -> None:
    database_key = _database_key(database)
    with _submission_failures_lock:
        failures = {
            key: code for key, code in _submission_failures.items()
            if key[0] == database_key
        }
    if not failures:
        return
    connection = connect_database(database, timeout=5)
    try:
        with connection:
            connection.executemany(
                "UPDATE summary_generation_submissions SET status = 'FAILED', error_code = ? "
                "WHERE id = ? AND status = 'PREPARING'",
                [(code, key[1]) for key, code in failures.items()],
            )
    finally:
        connection.close()
    with _submission_failures_lock:
        for key, code in failures.items():
            if _submission_failures.get(key) == code:
                _submission_failures.pop(key)


def _safe_submission(row: sqlite3.Row) -> dict:
    return {
        "submissionId": row["id"], "jobId": None,
        "projectId": row["project_id"], "skill": row["skill"],
        "status": row["status"], "sourceCount": 0,
        "completedBatches": 0, "totalBatches": 0, "progress": 0,
        "errorCode": row["error_code"], "version": None, "retryable": False,
        "createdAt": row["created_at"],
    }


def run_summary_submission(
    database: Path, *, submission_id: str, project_id: str, skill: str,
    request: dict, create,
) -> dict:
    """Reserve a durable receipt before preparation; never execute the same ID twice."""
    if (not isinstance(submission_id, str) or not submission_id.strip()
            or len(submission_id) > 128):
        raise ValueError("submissionId must contain 1-128 characters")
    _reconcile_submission_failures(database)
    encoded = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    connection = connect_database(database, timeout=5)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM summary_generation_submissions WHERE id = ?", (submission_id,),
            ).fetchone()
            if existing is not None:
                if (existing["project_id"] != project_id or existing["skill"] != skill
                        or existing["request_json"] != encoded):
                    raise ValueError("submissionId was already used for a different request")
            else:
                try:
                    connection.execute(
                        "INSERT INTO summary_generation_submissions "
                        "(id, project_id, skill, request_json, status, created_at) "
                        "VALUES (?, ?, ?, ?, 'PREPARING', ?)",
                        (submission_id, project_id, skill, encoded, _now()),
                    )
                except sqlite3.IntegrityError as error:
                    raise ValueError("a Summary submission is already preparing for this project and Skill") from error
    finally:
        connection.close()
    if existing is not None:
        return summary_job_status(database, submission_id=submission_id)
    try:
        result = create()
        return {**result, "submissionId": submission_id}
    except Exception as error:
        with _submission_failures_lock:
            _submission_failures[(_database_key(database), submission_id)] = _safe_error_code(error)
        try:
            _reconcile_submission_failures(database)
        except (OSError, sqlite3.Error):
            # Retain the terminal outcome for a later read or reservation, and
            # preserve the preparation error instead of replacing it with IO.
            pass
        raise


def summary_job_status(
    database: Path, *, job_id: str | None = None,
    project_id: str | None = None, skill: str | None = None, submission_id: str | None = None,
) -> dict | None:
    _reconcile_submission_failures(database)
    _reconcile_worker_failures(database)
    connection = connect_database(database, timeout=5)
    try:
        submission = None
        if submission_id:
            submission = connection.execute(
                "SELECT * FROM summary_generation_submissions WHERE id = ?", (submission_id,),
            ).fetchone()
            if submission is None:
                return None
            if submission["status"] != "ACCEPTED":
                return _safe_submission(submission)
            job_id = submission["job_id"]
        if job_id:
            row = connection.execute(
                "SELECT * FROM summary_generation_jobs WHERE id = ?", (job_id,),
            ).fetchone()
        elif project_id and skill:
            row = connection.execute(
                "SELECT * FROM summary_generation_jobs WHERE project_id = ? AND skill = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id, skill),
            ).fetchone()
            latest_submission = connection.execute(
                "SELECT * FROM summary_generation_submissions WHERE project_id = ? AND skill = ? "
                "ORDER BY created_at DESC LIMIT 1", (project_id, skill),
            ).fetchone()
            if (latest_submission is not None and latest_submission["status"] != "ACCEPTED"
                    and (row is None or row["status"] not in {"PENDING", "RUNNING"})
                    and (row is None or latest_submission["created_at"] > row["created_at"])):
                return _safe_submission(latest_submission)
        else:
            raise ValueError("jobId or projectId and skill are required")
        if row is None:
            if submission is not None:
                result = _safe_submission(submission)
                result.update(status="INTERRUPTED", errorCode="SUMMARY_JOB_DELETED")
                return result
            return None
        version = None
        if row["summary_id"]:
            version_row = connection.execute(
                "SELECT version FROM learning_summaries WHERE id = ?", (row["summary_id"],),
            ).fetchone()
            version = int(version_row[0]) if version_row is not None else None
        result = _safe_job(row, version)
        if submission is not None:
            result["submissionId"] = submission["id"]
        return result
    finally:
        connection.close()


def interrupt_stale_jobs(database: Path) -> int:
    connection = connect_database(database, timeout=5)
    try:
        with connection:
            interrupted = connection.execute(
                "UPDATE summary_generation_jobs SET status = 'INTERRUPTED', "
                "error_code = 'SERVICE_RESTARTED', completed_at = ? "
                "WHERE status IN ('PENDING', 'RUNNING')",
                (_now(),),
            ).rowcount
            interrupted += connection.execute(
                "UPDATE summary_generation_submissions SET status = 'INTERRUPTED', "
                "error_code = 'SERVICE_RESTARTED' WHERE status = 'PREPARING'",
            ).rowcount
            return interrupted
    finally:
        connection.close()


def _run_in_background(
    database: Path, *, job_id: str, skill_text: str, call_llm: CallLlm,
) -> None:
    try:
        run_summary_generation_job(
            database, job_id=job_id, skill_text=skill_text,
            call_llm=call_llm,
        )
    except Exception:
        # The pipeline normally persists its own terminal state. Cover failures
        # that happen before that error boundary without overwriting a state
        # committed by the worker or an interrupting service lifecycle event.
        _remember_worker_failure(database, job_id)
        try:
            _reconcile_worker_failures(database)
        except (OSError, sqlite3.Error):
            pass


def start_summary_job(
    database: Path, *, project_id: str, skill: str, skill_text: str,
    model: str, call_llm: CallLlm, window_months: int = 6,
    language: str = "zh-CN", provider_identity: str = "", submission_id: str | None = None,
) -> dict:
    _reconcile_worker_failures(database)
    job = create_summary_generation_job(
        database, project_id=project_id, skill=skill, skill_text=skill_text,
        model=model, window_months=window_months, language=language,
        provider_identity=provider_identity,
        submission_id=submission_id,
    )
    thread = threading.Thread(
        target=_run_in_background,
        kwargs={
            "database": database, "job_id": job["jobId"], "skill_text": skill_text,
            "call_llm": call_llm,
        },
        name=f"forge-summary-{job['jobId']}", daemon=True,
    )
    try:
        thread.start()
    except RuntimeError:
        connection = connect_database(database, timeout=5)
        try:
            with connection:
                connection.execute(
                    "UPDATE summary_generation_jobs SET status = 'INTERRUPTED', "
                    "error_code = 'WORKER_START_FAILED', completed_at = ? "
                    "WHERE id = ? AND status = 'PENDING'",
                    (_now(), job["jobId"]),
                )
        finally:
            connection.close()
        raise
    return {
        "jobId": job["jobId"], "projectId": project_id, "skill": skill,
        "language": language, "status": "PENDING", "sourceCount": job["sourceCount"],
        "completedBatches": 0, "totalBatches": 0, "progress": 0.0,
        "errorCode": None, "summaryId": None, "version": None,
        "retryable": False,
    }


def retry_summary_job(
    database: Path, *, previous_job_id: str, skill_text: str,
    model: str, call_llm: CallLlm, provider_identity: str = "", submission_id: str | None = None,
) -> dict:
    connection = connect_database(database, timeout=5)
    try:
        previous = connection.execute(
            "SELECT project_id, skill, status, window_months, language "
            "FROM summary_generation_jobs WHERE id = ?",
            (previous_job_id,),
        ).fetchone()
        if previous is None:
            raise ValueError("Summary generation job not found")
        if previous["status"] not in RETRYABLE_STATUSES:
            raise ValueError("only failed or interrupted Summary generation jobs can be retried")
        project_id, skill = previous["project_id"], previous["skill"]
        window_months = int(previous["window_months"])
        language = previous["language"]
    finally:
        connection.close()
    return start_summary_job(
        database, project_id=project_id, skill=skill, skill_text=skill_text,
        model=model, call_llm=call_llm, window_months=window_months,
        language=language,
        provider_identity=provider_identity,
        submission_id=submission_id,
    )
