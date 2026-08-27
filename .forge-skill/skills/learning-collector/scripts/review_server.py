#!/usr/bin/env python3
"""Serve the local cross-project learning review dashboard."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "project-registry.json"
HTML_PATH = SKILL_ROOT / "assets" / "review.html"
ALLOWED_ACTIONS = {"ACTIVE", "EXCLUDED", "DELETED"}
SERVICE_TOKEN = ""


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


def query_records(query: dict[str, list[str]]) -> list[dict]:
    project_filter = query.get("project", [""])[0]
    skill_filter = query.get("skill", [""])[0]
    status_filter = query.get("status", [""])[0]
    search = query.get("q", [""])[0].strip()
    try:
        limit = min(max(int(query.get("limit", ["200"])[0]), 1), 1000)
    except ValueError:
        limit = 200
    records = []
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
        connection = sqlite3.connect(database, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM learning_records" + where + " ORDER BY captured_at DESC LIMIT ?",
                (*values, limit),
            ).fetchall()
        finally:
            connection.close()
        for row in rows:
            item = dict(row)
            for field in ("output_json", "diagnostics_json", "metadata_json", "evaluation_json"):
                item[field.removesuffix("_json")] = decode_json(item.pop(field))
            records.append(item)
    records.sort(key=lambda item: item["captured_at"], reverse=True)
    return records[:limit]


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
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
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
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/review":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(length))
            if not update_record(payload):
                self.send_json({"error": "record not found or invalid action"}, 400)
                return
            self.send_json({"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

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
