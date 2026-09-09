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
import urllib.error
import urllib.request
try:
    import winreg
except ImportError:
    winreg = None
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from summary_engine import build_summary, encoded_size

SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "project-registry.json"
HTML_PATH = SKILL_ROOT / "assets" / "review.html"
VERSIONS_PATH = SKILL_ROOT / "assets" / "versions.html"
LLM_CONFIG_PATH = SKILL_ROOT / "llm-refiner.json"
_LLM_CONFIG_LOCK = threading.Lock()
MAX_LLM_RESPONSE_BYTES = 256 * 1024
ALLOWED_ACTIONS = {"ACTIVE", "EXCLUDED", "DELETED"}
SERVICE_TOKEN = ""
_QUERY_WARNINGS = threading.local()


def _warnings() -> list[dict]:
    if not hasattr(_QUERY_WARNINGS, "items"):
        _QUERY_WARNINGS.items = []
    return _QUERY_WARNINGS.items


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def llm_config() -> dict:
    defaults = {"enabled": False, "endpoint": "", "model": "", "wireApi": "responses", "apiKeyEnv": "FORGE_LEARNING_LLM_API_KEY", "timeoutSeconds": 30}
    try:
        value = json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**defaults, **value} if isinstance(value, dict) else defaults
    except (OSError, json.JSONDecodeError):
        return defaults


def llm_config_status() -> dict:
    config = llm_config()
    enabled = config.get("enabled") is True
    endpoint = config.get("endpoint") if isinstance(config.get("endpoint"), str) else ""
    model = config.get("model") if isinstance(config.get("model"), str) else ""
    api_key_env = config.get("apiKeyEnv") if isinstance(config.get("apiKeyEnv"), str) else ""
    valid_wire_api = config.get("wireApi") in {"responses", "chat_completions"}
    configured = bool(enabled and endpoint.strip() and model.strip() and valid_wire_api and api_key_env.strip() and _environment_value(api_key_env))
    return {**config, "configured": configured}


def _environment_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, name)
                return str(value) if value else None
        except (FileNotFoundError, OSError):
            pass
    return None


def save_llm_config(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("LLM configuration must be a JSON object")
    with _LLM_CONFIG_LOCK:
        # Lock the complete read-modify-write sequence so a toggle and a form
        # save cannot overwrite each other's fields with stale snapshots.
        config = llm_config()
        for key in ("enabled", "endpoint", "model", "wireApi", "apiKeyEnv", "timeoutSeconds"):
            if key in payload:
                config[key] = payload[key]
        if not isinstance(config["enabled"], bool) or not isinstance(config["endpoint"], str) or not isinstance(config["model"], str):
            raise ValueError("invalid LLM configuration")
        if config["wireApi"] not in {"responses", "chat_completions"}:
            raise ValueError("wireApi must be responses or chat_completions")
        if not isinstance(config["apiKeyEnv"], str) or not config["apiKeyEnv"].strip():
            raise ValueError("apiKeyEnv is required")
        if not isinstance(config["timeoutSeconds"], int) or not 5 <= config["timeoutSeconds"] <= 120:
            raise ValueError("timeoutSeconds must be between 5 and 120")
        temporary = LLM_CONFIG_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(LLM_CONFIG_PATH)
    return {**config, "configured": bool(config["enabled"] and config["endpoint"] and config["model"] and _environment_value(config["apiKeyEnv"]))}


def refine_summary(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("refinement request must be a JSON object")
    project_id, skill, version = payload.get("projectId"), payload.get("skill"), payload.get("version")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not isinstance(version, int):
        raise ValueError("projectId, skill and integer version are required")
    config = llm_config()
    if (config.get("enabled") is not True or not isinstance(config.get("endpoint"), str)
            or not config["endpoint"].strip() or not isinstance(config.get("model"), str)
            or not config["model"].strip() or config.get("wireApi") not in {"responses", "chat_completions"}):
        raise ValueError("LLM refinement is disabled or not configured")
    api_key_env = config.get("apiKeyEnv")
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise ValueError("LLM credential environment variable is invalid")
    api_key = _environment_value(api_key_env)
    if not api_key:
        raise ValueError(f"LLM credential environment variable is missing: {config['apiKeyEnv']}")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    connection = sqlite3.connect(Path(str(project.get("database", ""))), timeout=5)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS learning_summary_rule_sources (
                summary_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                record_id TEXT NOT NULL,
                PRIMARY KEY(summary_id, rule_id, record_id)
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_summary_rule_source_record "
            "ON learning_summary_rule_sources(record_id)"
        )
        row = connection.execute("SELECT summary_json, applied FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?", (project_id, skill, version)).fetchone()
        if row is None:
            raise ValueError("summary version not found")
        if row[1]:
            raise ValueError("an enabled summary cannot be refined")
        snapshot = decode_json(row[0])
        if not isinstance(snapshot, dict) or snapshot.get("status") != "DRAFT":
            raise ValueError("only DRAFT summaries can be refined")
        rules = snapshot.get("rules") if isinstance(snapshot.get("rules"), list) else []
        source_ids = {source_id for rule in rules for source_id in rule.get("sourceRecordIds", []) if isinstance(rule, dict)}
        source_rows = connection.execute("SELECT record_id FROM learning_summary_sources WHERE summary_id = (SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?)", (project_id, skill, version)).fetchall()
        source_ids = {row[0] for row in source_rows}
        prompt = {"task": "Refine Skill training candidates conservatively. Return JSON only.", "skill": skill, "rules": rules, "constraints": ["Do not invent evidence or sources", "Every rule must cite at least one sourceRecordId", "Only use sourceRecordIds from the input", "Return at most 12 rules", "All rules must have status PENDING", "Identify conflicts instead of merging contradictory instructions"]}
        instruction = "You are a conservative Skill-training editor. Output a JSON object with a rules array. Each rule needs id, stage, type, title, instruction, rationale, status, supportCount, sourceRecordIds, confidence. Every rule must cite at least one sourceRecordId."
        if config["wireApi"] == "responses":
            request_payload = {"model": config["model"], "temperature": 0, "input": [{"role": "system", "content": [{"type": "input_text", "text": instruction}]}, {"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}]}]}
        else:
            request_payload = {"model": config["model"], "temperature": 0, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}]}
        request_body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(config["endpoint"], data=request_body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=config["timeoutSeconds"]) as response:
                chunks, total = [], 0
                while True:
                    chunk = response.read(min(16 * 1024, MAX_LLM_RESPONSE_BYTES - total + 1))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MAX_LLM_RESPONSE_BYTES:
                        raise ValueError("LLM response exceeds the 256 KB limit")
                response_value = json.loads(b"".join(chunks).decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(f"LLM refinement failed: {type(error).__name__}") from error
        if config["wireApi"] == "responses":
            content = response_value.get("output_text") if isinstance(response_value, dict) else None
            if not content and isinstance(response_value, dict):
                content = "".join(item.get("text", "") for output in response_value.get("output", []) for item in output.get("content", []) if isinstance(item, dict))
        else:
            content = response_value.get("choices", [{}])[0].get("message", {}).get("content") if isinstance(response_value, dict) else None
        refined = json.loads(content) if isinstance(content, str) else content
        if not isinstance(refined, dict) or not isinstance(refined.get("rules"), list) or not 1 <= len(refined["rules"]) <= 12:
            raise ValueError("LLM returned invalid rules")
        seen = set()
        for rule in refined["rules"]:
            if not isinstance(rule, dict) or not isinstance(rule.get("id"), str) or rule["id"] in seen:
                raise ValueError("LLM returned duplicate or invalid rule IDs")
            seen.add(rule["id"])
            if rule.get("status") != "PENDING" or rule.get("stage") not in {"PRE_CHECK", "FINAL_VALIDATION"}:
                raise ValueError("LLM may only return pending valid stages")
            source_record_ids = rule.get("sourceRecordIds")
            if (not isinstance(source_record_ids, list) or not source_record_ids
                    or any(not isinstance(source_id, str) for source_id in source_record_ids)
                    or len(source_record_ids) != len(set(source_record_ids))
                    or not set(source_record_ids).issubset(source_ids)):
                raise ValueError("LLM returned unknown source IDs")
            if not isinstance(rule.get("instruction"), str) or not 1 <= len(rule["instruction"].strip()) <= 500:
                raise ValueError("LLM returned invalid instruction")
        snapshot["rules"] = refined["rules"]
        snapshot["statistics"]["generatedRules"] = len(refined["rules"])
        snapshot["refinement"] = {"mode": "explicit_llm", "model": config["model"], "refinedAt": now()}
        if encoded_size(snapshot) > 20_000:
            raise ValueError("refined summary exceeds the 20 KB quality limit")
        with connection:
            summary_id = connection.execute("SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?", (project_id, skill, version)).fetchone()[0]
            connection.execute("UPDATE learning_summaries SET summary_json = ? WHERE project_id = ? AND skill = ? AND version = ?", (json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), project_id, skill, version))
            connection.execute("DELETE FROM learning_summary_rule_sources WHERE summary_id = ?", (summary_id,))
            connection.executemany("INSERT INTO learning_summary_rule_sources(summary_id, rule_id, record_id) VALUES (?, ?, ?)", ((summary_id, rule["id"], source_id) for rule in refined["rules"] for source_id in rule["sourceRecordIds"]))
        return {"projectId": project_id, "skill": skill, "version": version, "status": "DRAFT", "summary": snapshot}
    finally:
        connection.close()


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


def create_summary(payload: dict) -> dict:
    project_id = payload.get("projectId")
    skill = payload.get("skill")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not skill.strip():
        raise ValueError("projectId and skill are required")
    skill = skill.strip().removeprefix("skill.").replace("_", "-")
    try:
        window_months = int(payload.get("windowMonths", 6))
    except (TypeError, ValueError):
        raise ValueError("windowMonths must be an integer")
    if not 1 <= window_months <= 120:
        raise ValueError("windowMonths must be between 1 and 120")
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
            record_columns = {row[1] for row in connection.execute("PRAGMA table_info(learning_records)")}
            if "is_classic" not in record_columns:
                connection.execute("ALTER TABLE learning_records ADD COLUMN is_classic INTEGER NOT NULL DEFAULT 0")
            if "classic_reason" not in record_columns:
                connection.execute("ALTER TABLE learning_records ADD COLUMN classic_reason TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_summaries (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, skill TEXT NOT NULL,
                    version INTEGER NOT NULL, created_at TEXT NOT NULL, source_count INTEGER NOT NULL,
                    summary_json TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(project_id, skill, version)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_summary_sources (
                    summary_id TEXT NOT NULL, record_id TEXT NOT NULL,
                    PRIMARY KEY(summary_id, record_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_summary_rule_sources (
                    summary_id TEXT NOT NULL, rule_id TEXT NOT NULL, record_id TEXT NOT NULL,
                    PRIMARY KEY(summary_id, rule_id, record_id)
                )"""
            )
            rows = connection.execute(
                """SELECT id, run_id, captured_at, output_json, edited_content, review_note,
                          is_classic, classic_reason
                   FROM learning_records WHERE project_id = ? AND skill = ?
                   AND review_status = 'ACTIVE' AND reviewed = 1
                   AND (output_json IS NOT NULL OR (edited_content IS NOT NULL AND trim(edited_content) <> ''))
                   ORDER BY captured_at ASC""",
                (project_id, skill),
            ).fetchall()
            if not rows:
                raise ValueError("no reviewed active records to summarize")
            latest = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM learning_summaries WHERE project_id = ? AND skill = ?",
                (project_id, skill),
            ).fetchone()[0]
            version = int(latest) + 1
            cutoff = datetime.now(timezone.utc).timestamp() - window_months * 30 * 86400
            source_records = []
            window_records = 0
            classic_records = 0
            for row in rows:
                try:
                    captured_timestamp = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00")).timestamp()
                except (TypeError, ValueError, OverflowError):
                    captured_timestamp = 0
                if not row["is_classic"] and captured_timestamp < cutoff:
                    continue
                window_records += 1
                classic_records += int(bool(row["is_classic"]))
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
                source_records.append({
                    "recordId": row["id"], "runId": row["run_id"],
                    "capturedAt": row["captured_at"], "content": content,
                    "reviewNote": note,
                })
            if not source_records:
                raise ValueError("no meaningful reviewed active records to summarize")
            refined = build_summary(source_records, skill=skill)
            snapshot = {
                "format": "forge-skill-training-summary-v5",
                "projectId": project_id, "skill": skill, "version": version,
                "sourceCount": len(source_records),
                "window": {"months": window_months, "windowRecords": window_records,
                           "classicRecords": classic_records, "cutoffAt": datetime.fromtimestamp(cutoff, timezone.utc).isoformat().replace("+00:00", "Z")},
                **refined,
            }
            while encoded_size(snapshot) > 20_000 and snapshot["rules"]:
                snapshot["rules"].pop()
                snapshot["statistics"]["generatedRules"] = len(snapshot["rules"])
                snapshot["statistics"]["discardedClusters"] += 1
            if encoded_size(snapshot) > 20_000:
                raise ValueError("summary metadata exceeds the 20 KB quality limit")
            created_at = now()
            summary_id = f"summary-{uuid.uuid4()}"
            connection.execute(
                """INSERT INTO learning_summaries
                   (id, project_id, skill, version, created_at, source_count, summary_json, applied)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (summary_id, project_id, skill, version, created_at,
                 len(source_records), json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))),
            )
            connection.executemany(
                "INSERT INTO learning_summary_sources(summary_id, record_id) VALUES (?, ?)",
                ((summary_id, record["recordId"]) for record in source_records),
            )
            return {"projectId": project_id, "skill": skill, "version": version,
                    "createdAt": created_at, "sourceCount": len(source_records), "applied": False,
                    "summary": snapshot}
    finally:
        connection.close()


def apply_summary(payload: dict) -> dict:
    project_id, skill, version = payload.get("projectId"), payload.get("skill"), payload.get("version")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not isinstance(version, int):
        raise ValueError("projectId, skill and integer version are required")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None or skill not in _enabled_skills(project):
        raise ValueError("project or enabled skill not found")
    database = Path(str(project.get("database", "")))
    connection = sqlite3.connect(database, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT summary_json FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError("summary version not found")
            snapshot = decode_json(row["summary_json"])
            if not isinstance(snapshot, dict) or snapshot.get("format") not in {"forge-skill-training-summary-v4", "forge-skill-training-summary-v5"}:
                raise ValueError("legacy summary versions cannot be newly enabled; generate and review a current version")
            if snapshot.get("status") != "REVIEWED":
                raise ValueError("summary rules must be fully reviewed before enabling")
            if not any(rule.get("status") == "CONFIRMED" for rule in snapshot.get("rules", [])):
                raise ValueError("at least one confirmed rule is required before enabling")
            connection.execute("UPDATE learning_summaries SET applied = 0 WHERE project_id = ? AND skill = ?", (project_id, skill))
            connection.execute("UPDATE learning_summaries SET applied = 1 WHERE project_id = ? AND skill = ? AND version = ?", (project_id, skill, version))
            applied_dir = Path(str(project.get("path", ""))) / ".forge-skill" / "learning" / "applied"
            applied_dir.mkdir(parents=True, exist_ok=True)
            target = applied_dir / f"{skill}.json"
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(target)
            return {"projectId": project_id, "skill": skill, "version": version, "applied": True}
    finally:
        connection.close()


def review_summary(payload: dict) -> dict:
    project_id, skill, version = payload.get("projectId"), payload.get("skill"), payload.get("version")
    updates = payload.get("rules")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not isinstance(version, int):
        raise ValueError("projectId, skill and integer version are required")
    if not isinstance(updates, list):
        raise ValueError("rules must be an array")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    connection = sqlite3.connect(Path(str(project.get("database", ""))), timeout=5)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT summary_json, applied FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError("summary version not found")
            if row[1]:
                raise ValueError("an enabled summary cannot be edited; create a new version")
            snapshot = decode_json(row[0])
            if not isinstance(snapshot, dict) or snapshot.get("format") not in {"forge-skill-training-summary-v4", "forge-skill-training-summary-v5"}:
                raise ValueError("legacy summary versions cannot be reviewed")
            originals = {rule.get("id"): rule for rule in snapshot.get("rules", []) if isinstance(rule, dict)}
            if (len(updates) != len(originals)
                    or any(not isinstance(item, dict) for item in updates)
                    or {item.get("id") for item in updates} != set(originals)):
                raise ValueError("review must include every generated rule exactly once")
            for update in updates:
                rule = originals[update["id"]]
                status = update.get("status")
                stage = update.get("stage")
                instruction = str(update.get("instruction") or "").strip()
                if status not in {"PENDING", "CONFIRMED", "EXCLUDED"}:
                    raise ValueError("invalid rule status")
                if stage not in {"PRE_CHECK", "FINAL_VALIDATION"}:
                    raise ValueError("invalid rule stage")
                if not instruction or len(instruction) > 500:
                    raise ValueError("rule instruction must contain 1-500 characters")
                rule.update({"status": status, "stage": stage, "instruction": instruction})
            rules = list(originals.values())
            counts = {status: sum(rule["status"] == status for rule in rules)
                      for status in ("PENDING", "CONFIRMED", "EXCLUDED")}
            snapshot["rules"] = rules
            snapshot["statistics"].update({
                "pendingRules": counts["PENDING"], "confirmedRules": counts["CONFIRMED"],
                "excludedRules": counts["EXCLUDED"],
            })
            snapshot["status"] = "REVIEWED" if counts["PENDING"] == 0 else "DRAFT"
            snapshot["reviewedAt"] = now() if snapshot["status"] == "REVIEWED" else None
            if encoded_size(snapshot) > 20_000:
                raise ValueError("reviewed summary exceeds the 20 KB quality limit")
            connection.execute(
                "UPDATE learning_summaries SET summary_json = ? WHERE project_id = ? AND skill = ? AND version = ?",
                (json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), project_id, skill, version),
            )
            return {"projectId": project_id, "skill": skill, "version": version,
                    "status": snapshot["status"], "statistics": snapshot["statistics"]}
    finally:
        connection.close()


def delete_summary(payload: dict) -> dict:
    project_id, skill, version = payload.get("projectId"), payload.get("skill"), payload.get("version")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not isinstance(version, int):
        raise ValueError("projectId, skill and integer version are required")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    database = Path(str(project.get("database", "")))
    connection = sqlite3.connect(database, timeout=5)
    try:
        with connection:
            row = connection.execute(
                "SELECT applied FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError("summary version not found")
            if row[0]:
                raise ValueError("cannot delete the applied version; apply another version first")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_summary_sources (
                    summary_id TEXT NOT NULL, record_id TEXT NOT NULL,
                    PRIMARY KEY(summary_id, record_id)
                )"""
            )
            summary_id = connection.execute(
                "SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()[0]
            connection.execute("DELETE FROM learning_summary_sources WHERE summary_id = ?", (summary_id,))
            connection.execute("DELETE FROM learning_summary_rule_sources WHERE summary_id = ?", (summary_id,))
            cursor = connection.execute(
                "DELETE FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            )
            return {"projectId": project_id, "skill": skill, "version": version, "deleted": cursor.rowcount == 1}
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
    connection = sqlite3.connect(database, timeout=5)
    try:
        with connection:
            if action == "DELETED":
                cursor = connection.execute(
                    "DELETE FROM learning_records WHERE id = ? AND project_id = ?",
                    (record_id, project_id),
                )
                return cursor.rowcount == 1
            reviewed_at = now()
            classic = payload.get("isClassic", False)
            if not isinstance(classic, bool):
                return False
            cursor = connection.execute(
            """
            UPDATE learning_records
            SET review_status = ?, reviewed = 1, edited_content = ?, review_note = ?,
                reviewed_at = ?, deleted_at = ?, is_classic = ?, classic_reason = ?
            WHERE id = ? AND project_id = ?
            """,
                (action, payload.get("editedContent"), str(payload.get("note") or ""), reviewed_at, None,
                 int(classic), str(payload.get("classicReason") or ""), record_id, project_id),
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
            elif parsed.path in {"/versions", "/versions.html"}:
                body = VERSIONS_PATH.read_bytes()
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
            elif parsed.path == "/api/llm-config":
                self.send_json(llm_config_status())
            else:
                self.send_json({"error": "not found"}, 404)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                self.send_json({"error": "database is busy; operation was not committed", "retryable": True}, 503)
            else:
                self.send_json({"error": str(error)}, 500)

    def do_POST(self):
        if self.path not in {"/api/review", "/api/summarize", "/api/apply", "/api/delete-summary", "/api/review-summary", "/api/llm-config", "/api/refine"}:
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/llm-config":
                self.send_json(save_llm_config(payload))
                return
            if self.path == "/api/refine":
                self.send_json(refine_summary(payload))
                return
            if self.path == "/api/summarize":
                self.send_json(create_summary(payload), 201)
                return
            if self.path == "/api/apply":
                self.send_json(apply_summary(payload))
                return
            if self.path == "/api/delete-summary":
                self.send_json(delete_summary(payload))
                return
            if self.path == "/api/review-summary":
                self.send_json(review_summary(payload))
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
