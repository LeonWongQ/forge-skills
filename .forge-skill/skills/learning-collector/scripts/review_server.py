#!/usr/bin/env python3
"""Serve the local cross-project learning review dashboard."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "project-registry.json"
HTML_PATH = SKILL_ROOT / "assets" / "review.html"
ALLOWED_ACTIONS = {"ACTIVE", "EXCLUDED", "DELETED"}
SERVICE_TOKEN = ""
_QUERY_WARNINGS = threading.local()


def _warnings() -> list[dict]:
    if not hasattr(_QUERY_WARNINGS, "items"):
        _QUERY_WARNINGS.items = []
    return _QUERY_WARNINGS.items


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def projects() -> list[dict]:
    try:
        value = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    result = []
    for item in value.get("projects", []):
        if not isinstance(item, dict):
            continue
        project = dict(item)
        project["projectId"] = project.get("projectId", project.get("id"))
        configured = project.get("status")
        if configured not in {"CONFLICT", "DISABLED"}:
            path = Path(str(project.get("path", "")))
            database = Path(str(project.get("database", "")))
            project["status"] = "ACTIVE" if path.is_dir() and database.is_file() else "UNAVAILABLE"
        result.append(project)
    return result


def decode_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def has_meaningful_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_meaningful_content(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_meaningful_content(item) for item in value)
    return True


def query_records(query: dict[str, list[str]]) -> list[dict]:
    _warnings().clear()
    project_filter = query.get("project", [""])[0]
    skill_filter = query.get("skill", [""])[0]
    status_filter = query.get("status", [""])[0]
    search = query.get("q", [""])[0].strip()
    try:
        limit = min(max(int(query.get("limit", ["200"])[0]), 1), 1000)
    except ValueError:
        limit = 200
    try:
        offset = max(int(query.get("offset", ["0"])[0]), 0)
    except ValueError:
        offset = 0
    records = []
    fetch_limit = limit + offset
    for project in projects():
        if project_filter and project.get("projectId") != project_filter:
            continue
        database = Path(str(project.get("database", "")))
        if not database.is_file():
            continue
        clauses, values = [], []
        if skill_filter:
            clauses.append("skill = ?")
            values.append(skill_filter)
        if status_filter:
            clauses.append("review_status = ?")
            values.append(status_filter)
        if search:
            clauses.append("(output_json LIKE ? OR edited_content LIKE ? OR review_note LIKE ? OR run_id LIKE ?)")
            values.extend([f"%{search}%"] * 4)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            connection = sqlite3.connect(database, timeout=5)
            try:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM learning_records" + where + " ORDER BY captured_at DESC LIMIT ? OFFSET ?",
                    (*values, fetch_limit, 0),
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            _warnings().append({"projectId": project.get("projectId"), "path": project.get("path"), "error": "database unavailable"})
            continue
        for row in rows:
            item = dict(row)
            for field in ("output_json", "diagnostics_json", "metadata_json", "evaluation_json"):
                item[field.removesuffix("_json")] = decode_json(item.pop(field))
            records.append(item)
    records.sort(key=lambda item: item["captured_at"], reverse=True)
    return records[offset:offset + limit]


def query_summaries(query: dict[str, list[str]]) -> list[dict]:
    _warnings().clear()
    project_id = query.get("project", [""])[0]
    skill = query.get("skill", [""])[0]
    details = query.get("details", ["0"])[0] == "1"
    try:
        limit = min(max(int(query.get("limit", ["50"])[0]), 1), 200)
    except ValueError:
        limit = 50
    try:
        offset = max(int(query.get("offset", ["0"])[0]), 0)
    except ValueError:
        offset = 0
    result = []
    for project in projects():
        if project_id and project.get("projectId") != project_id:
            continue
        database = Path(str(project.get("database", "")))
        if not database.is_file():
            continue
        try:
            connection = sqlite3.connect(database, timeout=5)
            try:
                connection.row_factory = sqlite3.Row
                clauses, values = [], []
                if skill:
                    clauses.append("skill = ?")
                    values.append(skill)
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                has_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_summaries'"
                ).fetchone()
                rows = connection.execute(
                    "SELECT * FROM learning_summaries" + where + " ORDER BY skill, version DESC LIMIT ? OFFSET ?",
                    (*values, limit + offset, 0),
                ).fetchall() if has_table else []
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            _warnings().append({"projectId": project.get("projectId"), "path": project.get("path"), "error": "database unavailable"})
            continue
        for row in rows:
            item = dict(row)
            summary_json = item.pop("summary_json")
            if details:
                item["summary"] = decode_json(summary_json)
            result.append(item)
    result.sort(key=lambda item: (item.get("skill", ""), -int(item.get("version", 0))))
    return result[offset:offset + limit]


def extract_training_content(content, review_note: str) -> dict:
    """Normalize one reviewed result into a future Skill-training item.

    This is intentionally deterministic: it extracts useful user-visible
    fields without inventing rules or asking a model to reinterpret history.
    """
    if isinstance(content, dict):
        known = (
            "status", "conclusion", "overallAssessment", "assessment", "findings",
            "verification", "scope", "caveats", "openQuestions", "suggestedDirection",
        )
        extracted = {key: content[key] for key in known if key in content}
        if not extracted:
            extracted = {"content": content}
    else:
        extracted = {"content": content}
    if review_note.strip():
        extracted["reviewNote"] = review_note.strip()
    return extracted


def _enabled_skills(project: dict) -> set[str]:
    try:
        forge_root = SKILL_ROOT.parent.parent / "forge"
        if str(forge_root) not in sys.path:
            sys.path.insert(0, str(forge_root))
        from forge_cli.learning_collector import _load_enabled_skills
        enabled = _load_enabled_skills(forge_root, Path(str(project.get("path", ""))))
    except (ImportError, OSError, json.JSONDecodeError):
        return set()
    return enabled or set()


def build_training_profile(skill: str, items: list[dict]) -> dict:
    """Aggregate review evidence into a deterministic, skill-specific profile."""
    profile = {"skill": skill, "recordCount": len(items), "adjustmentCandidates": []}
    if skill == "code-review":
        severity_counts: dict[str, int] = {}
        finding_titles: dict[str, int] = {}
        findings = []
        for item in items:
            content = item["content"]
            if not isinstance(content, dict):
                continue
            values = content.get("findings")
            if not isinstance(values, list):
                continue
            for finding in values:
                if not isinstance(finding, dict):
                    continue
                severity = str(finding.get("severity") or "UNSPECIFIED")
                title = str(finding.get("title") or "UNTITLED")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                finding_titles[title] = finding_titles.get(title, 0) + 1
                findings.append({
                    "sourceRecordId": item["source"]["recordId"],
                    "title": finding.get("title"), "severity": finding.get("severity"),
                    "evidence": finding.get("evidence"),
                    "impact": finding.get("impact", finding.get("why_it_matters")),
                    "direction": finding.get("direction", finding.get("suggested_direction")),
                    "confidence": finding.get("confidence"),
                })
        profile["findingStats"] = {"bySeverity": severity_counts, "byTitle": finding_titles}
        profile["findings"] = findings
        notes = [item["content"].get("reviewNote") for item in items
                 if isinstance(item.get("content"), dict) and item["content"].get("reviewNote")]
        profile["reviewNotes"] = notes
        profile["adjustmentCandidates"] = []
        if finding_titles:
            profile["adjustmentCandidates"].append({
                "type": "recurring_finding",
                "status": "PENDING",
                "titles": [title for title, count in finding_titles.items() if count > 1],
                "evidence": "Repeated finding titles may indicate a check worth strengthening; confirm manually.",
            })
        if severity_counts:
            profile["adjustmentCandidates"].append({
                "type": "severity_calibration",
                "status": "PENDING",
                "distribution": severity_counts,
                "evidence": "Use reviewed severity distribution to inspect calibration; do not change thresholds automatically.",
            })
        if notes:
            profile["adjustmentCandidates"].append({
                "type": "reviewer_corrections",
                "status": "PENDING",
                "count": len(notes),
                "evidence": "Reviewer notes require manual confirmation before becoming Skill rules.",
            })
    else:
        profile["adjustmentCandidates"] = [
            {"status": "PENDING", "type": "manual_review",
             "evidence": "Review extracted records for recurring corrections before defining Skill-specific rules."}
        ]
    return profile


def create_summary(payload: dict) -> dict:
    project_id = payload.get("projectId")
    skill = payload.get("skill")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not skill.strip():
        raise ValueError("projectId and skill are required")
    skill = skill.strip().removeprefix("skill.").replace("_", "-")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    if skill.strip() not in _enabled_skills(project):
        raise ValueError("skill is not enabled for learning in this project")
    database = Path(str(project.get("database", "")))
    if not database.is_file():
        raise ValueError("project database is unavailable")
    connection = sqlite3.connect(database, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_summaries (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, skill TEXT NOT NULL,
                    version INTEGER NOT NULL, created_at TEXT NOT NULL, source_count INTEGER NOT NULL,
                    summary_json TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(project_id, skill, version)
                )"""
            )
            rows = connection.execute(
                """SELECT id, run_id, captured_at, output_json, edited_content, review_note
                   FROM learning_records WHERE project_id = ? AND skill = ?
                   AND review_status = 'ACTIVE'
                   AND (output_json IS NOT NULL OR (edited_content IS NOT NULL AND trim(edited_content) <> ''))
                   ORDER BY captured_at ASC""",
                (project_id, skill),
            ).fetchall()
            if not rows:
                raise ValueError("no active records to summarize")
            latest = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM learning_summaries WHERE project_id = ? AND skill = ?",
                (project_id, skill),
            ).fetchone()[0]
            version = int(latest) + 1
            entries = []
            training_items = []
            for row in rows:
                content = row["edited_content"]
                if not content:
                    content = decode_json(row["output_json"])
                elif isinstance(content, str):
                    # Review textareas store edits as text; restore JSON objects
                    # when the reviewer supplied a structured payload.
                    content = decode_json(content)
                note = row["review_note"] or ""
                if not has_meaningful_content(content):
                    continue
                source = {"recordId": row["id"], "projectId": project_id, "runId": row["run_id"], "capturedAt": row["captured_at"]}
                content_type = "json" if isinstance(content, (dict, list)) else "text"
                entries.append({**source, "content": content, "contentType": content_type, "reviewNote": note})
                training_items.append({"source": source, "content": extract_training_content(content, note), "contentType": content_type})
            snapshot = {
                "format": "forge-skill-training-summary-v2",
                "projectId": project_id, "skill": skill, "version": version,
                "sourceCount": len(entries),
                "trainingProfile": build_training_profile(skill, training_items),
                "trainingContent": training_items,
                "sourceRecords": entries,
            }
            created_at = now()
            connection.execute(
                "UPDATE learning_summaries SET applied = 0 WHERE project_id = ? AND skill = ?",
                (project_id, skill),
            )
            connection.execute(
                """INSERT INTO learning_summaries
                   (id, project_id, skill, version, created_at, source_count, summary_json, applied)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (f"summary-{uuid.uuid4()}", project_id, skill, version, created_at,
                 len(entries), json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))),
            )
            return {"projectId": project_id, "skill": skill, "version": version,
                    "createdAt": created_at, "sourceCount": len(entries), "applied": True,
                    "summary": snapshot}
    finally:
        connection.close()


def update_record(payload: dict) -> bool:
    project_id = payload.get("projectId")
    record_id = payload.get("recordId")
    action = payload.get("action")
    if not isinstance(project_id, str) or not isinstance(record_id, str) or action not in ALLOWED_ACTIONS:
        return False
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        return False
    database = Path(str(project.get("database", "")))
    if not database.is_file():
        return False
    reviewed_at = now()
    deleted_at = reviewed_at if action == "DELETED" else None
    connection = sqlite3.connect(database, timeout=5)
    try:
        with connection:
            cursor = connection.execute(
            """
            UPDATE learning_records
            SET review_status = ?, reviewed = 1, edited_content = ?, review_note = ?,
                reviewed_at = ?, deleted_at = ?
            WHERE id = ? AND project_id = ?
            """,
                (action, payload.get("editedContent"), str(payload.get("note") or ""), reviewed_at, deleted_at, record_id, project_id),
            )
            return cursor.rowcount == 1
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=True).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if _warnings():
            self.send_header("X-Unavailable-Projects", json.dumps(_warnings(), ensure_ascii=True))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/projects":
                self.send_json(projects())
            elif parsed.path == "/api/service":
                self.send_json({"pid": os.getpid(), "token": SERVICE_TOKEN})
            elif parsed.path == "/api/records":
                self.send_json(query_records(parse_qs(parsed.query)))
            elif parsed.path == "/api/summaries":
                self.send_json(query_summaries(parse_qs(parsed.query)))
            else:
                self.send_json({"error": "not found"}, 404)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                self.send_json({"error": "database is busy; operation was not committed", "retryable": True}, 503)
            else:
                self.send_json({"error": str(error)}, 500)

    def do_POST(self):
        if self.path not in {"/api/review", "/api/summarize"}:
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/summarize":
                self.send_json(create_summary(payload), 201)
                return
            if not update_record(payload):
                self.send_json({"error": "record not found or invalid action"}, 400)
                return
            self.send_json({"ok": True})
        except (ValueError, json.JSONDecodeError, sqlite3.IntegrityError) as error:
            self.send_json({"error": str(error)}, 400)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                self.send_json({"error": "database is busy; operation was not committed", "retryable": True}, 503)
            else:
                self.send_json({"error": str(error)}, 500)

    def log_message(self, format, *args):
        return


def main():
    global SERVICE_TOKEN
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    SERVICE_TOKEN = args.token
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Learning review: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
