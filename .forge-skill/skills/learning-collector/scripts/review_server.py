#!/usr/bin/env python3
"""Serve the local cross-project learning review dashboard."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import socket
import sqlite3
import sys
import threading
import time
import uuid
import urllib.error
import urllib.request
try:
    import winreg
except ImportError:
    winreg = None
from datetime import datetime, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FORGE_ROOT = Path(__file__).absolute().parents[3] / "forge"
if str(FORGE_ROOT) not in sys.path:
    sys.path.insert(0, str(FORGE_ROOT))
from refinement_quality import evidence_packet
from forge_cli.data_paths import forge_data_root
from forge_cli.learning_collector import _registry_file_lock, connect_database
from forge_cli.learning_hook_manager import (
    configure_global_hook,
    global_hook_status,
    remove_global_hook,
)
from overlay_evaluator import evaluate_overlay, evaluation_readiness
from summary_generation_service import (
    interrupt_stale_jobs,
    retry_summary_job,
    run_summary_submission,
    start_summary_job,
    summary_job_status,
)
from llm_summary_pipeline import (
    LlmProviderError,
    LlmTimeoutError,
    LlmTransportError,
    estimate_summary_generation,
)

SKILL_ROOT = Path(__file__).absolute().parents[1]
DATA_ROOT = forge_data_root(FORGE_ROOT)
REGISTRY_PATH = DATA_ROOT / "project-registry.json"
LEGACY_REGISTRY_PATH = SKILL_ROOT / "project-registry.json"
HTML_PATH = SKILL_ROOT / "assets" / "review.html"
VERSIONS_PATH = SKILL_ROOT / "assets" / "versions.html"
OVERLAYS_PATH = SKILL_ROOT / "assets" / "overlays.html"
I18N_PATH = SKILL_ROOT / "assets" / "learning-i18n.js"
LLM_CONFIG_PATH = DATA_ROOT / "llm-refiner.json"
LEGACY_LLM_CONFIG_PATH = SKILL_ROOT / "llm-refiner.json"
SERVICE_OWNER_PATH = DATA_ROOT / "services" / "learning-review"
_LLM_CONFIG_LOCK = threading.Lock()
_PROJECT_REGISTRY_LOCK = threading.Lock()
MAX_LLM_RESPONSE_BYTES = 256 * 1024
MAX_LLM_ERROR_BODY_BYTES = 8 * 1024
MAX_LLM_ERROR_FIELD_CHARS = 500
MAX_LLM_STREAM_BYTES = 4 * 1024 * 1024
MAX_LLM_STREAM_DURATION_SECONDS = 180
ALLOWED_ACTIONS = {"ACTIVE", "EXCLUDED", "DELETED"}
OVERLAY_ROLLBACK_MIN_REVIEWS = 10
OVERLAY_ROLLBACK_NEGATIVE_RATE = 0.30
SERVICE_TOKEN = ""
SERVICE_COOKIE = "forge_learning_service"
_QUERY_WARNINGS = threading.local()


def _warnings() -> list[dict]:
    if not hasattr(_QUERY_WARNINGS, "items"):
        _QUERY_WARNINGS.items = []
    return _QUERY_WARNINGS.items


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _encoded_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _service_cookie() -> str:
    return f"{SERVICE_COOKIE}={SERVICE_TOKEN}; Path=/; HttpOnly; SameSite=Strict"


def _service_host_error(headers, port: int) -> tuple[int, str] | None:
    if str(headers.get("Host", "")).casefold() != f"127.0.0.1:{port}":
        return 403, "invalid service host"
    return None


def _mutation_request_error(headers, port: int) -> tuple[int, str] | None:
    expected_origin = f"http://127.0.0.1:{port}"
    host_error = _service_host_error(headers, port)
    if host_error is not None:
        return host_error
    origin = str(headers.get("Origin", ""))
    if origin and origin != expected_origin:
        return 403, "cross-origin mutation is not allowed"
    content_type = str(headers.get("Content-Type", "")).partition(";")[0].strip().casefold()
    if content_type != "application/json":
        return 415, "Content-Type must be application/json"
    try:
        cookies = SimpleCookie()
        cookies.load(str(headers.get("Cookie", "")))
        supplied = cookies[SERVICE_COOKIE].value if SERVICE_COOKIE in cookies else ""
    except CookieError:
        supplied = ""
    if not SERVICE_TOKEN or not hmac.compare_digest(supplied, SERVICE_TOKEN):
        return 403, "missing or invalid service token"
    return None


def llm_config() -> dict:
    defaults = {"enabled": False, "baseUrl": "", "model": "", "wireApi": "responses", "apiKeyEnv": "FORGE_LEARNING_LLM_API_KEY", "timeoutSeconds": 30}
    config_path = LLM_CONFIG_PATH if LLM_CONFIG_PATH.is_file() else LEGACY_LLM_CONFIG_PATH
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return defaults
        config = {**defaults, **value}
        configured_url = value.get("baseUrl", value.get("endpoint", ""))
        config["baseUrl"] = _normalize_llm_base_url(configured_url) if isinstance(configured_url, str) else ""
        config.pop("endpoint", None)
        return config
    except (OSError, json.JSONDecodeError):
        return defaults


def _normalize_llm_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    lowered = base_url.casefold()
    for suffix in ("/chat/completions", "/responses"):
        if lowered.endswith(suffix):
            return base_url[:-len(suffix)].rstrip("/")
    return base_url


def _llm_request_url(config: dict) -> str:
    configured_url = config.get("baseUrl", config.get("endpoint", ""))
    if not isinstance(configured_url, str):
        raise ValueError("LLM baseUrl is invalid")
    base_url = _normalize_llm_base_url(configured_url)
    if not base_url:
        raise ValueError("LLM baseUrl is required")
    suffix = "/responses" if config.get("wireApi") == "responses" else "/chat/completions"
    return base_url + suffix


def llm_config_status() -> dict:
    config = llm_config()
    enabled = config.get("enabled") is True
    base_url = config.get("baseUrl") if isinstance(config.get("baseUrl"), str) else ""
    model = config.get("model") if isinstance(config.get("model"), str) else ""
    api_key_env = config.get("apiKeyEnv") if isinstance(config.get("apiKeyEnv"), str) else ""
    valid_wire_api = config.get("wireApi") in {"responses", "chat_completions"}
    configured = bool(enabled and base_url.strip() and model.strip() and valid_wire_api and api_key_env.strip() and _environment_value(api_key_env))
    return {**config, "requestUrl": _llm_request_url(config) if base_url.strip() and valid_wire_api else "", "configured": configured}


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
        if "baseUrl" not in payload and "endpoint" in payload:
            payload = {**payload, "baseUrl": payload["endpoint"]}
        for key in ("enabled", "baseUrl", "model", "wireApi", "apiKeyEnv", "timeoutSeconds"):
            if key in payload:
                config[key] = payload[key]
        if not isinstance(config["enabled"], bool) or not isinstance(config["baseUrl"], str) or not isinstance(config["model"], str):
            raise ValueError("invalid LLM configuration")
        config["baseUrl"] = _normalize_llm_base_url(config["baseUrl"])
        if config["wireApi"] not in {"responses", "chat_completions"}:
            raise ValueError("wireApi must be responses or chat_completions")
        if not isinstance(config["apiKeyEnv"], str) or not config["apiKeyEnv"].strip():
            raise ValueError("apiKeyEnv is required")
        if not isinstance(config["timeoutSeconds"], int) or not 5 <= config["timeoutSeconds"] <= 120:
            raise ValueError("timeoutSeconds must be between 5 and 120")
        LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = LLM_CONFIG_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(LLM_CONFIG_PATH)
    return {**config, "requestUrl": _llm_request_url(config) if config["baseUrl"] else "", "configured": bool(config["enabled"] and config["baseUrl"] and config["model"] and _environment_value(config["apiKeyEnv"]))}


def _configured_llm() -> tuple[dict, str]:
    config = llm_config()
    if (config.get("enabled") is not True or not isinstance(config.get("baseUrl"), str)
            or not config["baseUrl"].strip() or not isinstance(config.get("model"), str)
            or not config["model"].strip() or config.get("wireApi") not in {"responses", "chat_completions"}):
        raise ValueError("LLM is disabled or not configured")
    api_key_env = config.get("apiKeyEnv")
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise ValueError("LLM credential environment variable is invalid")
    api_key = _environment_value(api_key_env)
    if not api_key:
        raise ValueError(f"LLM credential environment variable is missing: {api_key_env}")
    return config, api_key


def _llm_usage(response_value: dict, wire_api: str) -> dict:
    usage = response_value.get("usage")
    if not isinstance(usage, dict):
        return {"status": "unavailable", "reason": "backend_did_not_report_usage"}
    if wire_api == "responses":
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    values = (input_tokens, output_tokens, total_tokens)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        return {"status": "unavailable", "reason": "backend_reported_invalid_usage"}
    return {
        "status": "reported", "inputTokens": input_tokens,
        "outputTokens": output_tokens, "totalTokens": total_tokens,
    }


def _llm_http_error(error: urllib.error.HTTPError, api_key: str) -> str:
    """Return bounded provider diagnostics without exposing response bodies or credentials."""
    fields = []
    try:
        raw = error.read(MAX_LLM_ERROR_BODY_BYTES + 1)
    except OSError:
        raw = b""
    if len(raw) <= MAX_LLM_ERROR_BODY_BYTES:
        try:
            response_value = json.loads(raw.decode("utf-8")) if raw else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_value = None
        provider_error = response_value.get("error") if isinstance(response_value, dict) else None
        if isinstance(provider_error, dict):
            for key in ("message", "type", "code"):
                value = provider_error.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    normalized = " ".join(str(value).split())[:MAX_LLM_ERROR_FIELD_CHARS]
                    if api_key:
                        normalized = normalized.replace(api_key, "[REDACTED]")
                    if normalized:
                        fields.append(f"{key}={normalized}")
        elif isinstance(provider_error, str):
            normalized = " ".join(provider_error.split())[:MAX_LLM_ERROR_FIELD_CHARS]
            if api_key:
                normalized = normalized.replace(api_key, "[REDACTED]")
            if normalized:
                fields.append(f"message={normalized}")
    reason = " ".join(str(error.reason).split()) if error.reason else ""
    status = f"HTTP {error.code}" + (f" {reason}" if reason else "")
    request_id = error.headers.get("x-request-id") if error.headers else None
    if request_id:
        fields.append(f"requestId={str(request_id)[:128]}")
    return f"LLM request failed: {status}" + (f" ({'; '.join(fields)})" if fields else "")


def _responses_content(response_value: dict) -> str:
    content = response_value.get("output_text")
    if content is not None:
        if not isinstance(content, str):
            raise ValueError("LLM returned invalid Responses text")
        return content
    output_items = response_value.get("output")
    if not isinstance(output_items, list):
        raise ValueError("LLM returned invalid Responses output")
    text_parts = []
    for output_item in output_items:
        if not isinstance(output_item, dict):
            raise ValueError("LLM returned invalid Responses output")
        content_items = output_item.get("content", [])
        if not isinstance(content_items, list):
            raise ValueError("LLM returned invalid Responses content")
        for content_item in content_items:
            if not isinstance(content_item, dict):
                raise ValueError("LLM returned invalid Responses content")
            text = content_item.get("text")
            if text is not None and not isinstance(text, str):
                raise ValueError("LLM returned invalid Responses text")
            if text:
                text_parts.append(text)
    return "".join(text_parts)


def _read_json_response(response) -> dict:
    chunks, total = [], 0
    while True:
        chunk = response.read(min(16 * 1024, MAX_LLM_RESPONSE_BYTES - total + 1))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_LLM_RESPONSE_BYTES:
            raise ValueError("LLM response exceeds the 256 KB limit")
    value = json.loads(b"".join(chunks).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("LLM returned an invalid response object")
    return value


def _stream_error(event_type: str, payload: dict, api_key: str) -> LlmProviderError:
    response_value = payload.get("response") if isinstance(payload.get("response"), dict) else payload
    provider_error = response_value.get("error") if isinstance(response_value, dict) else None
    if not isinstance(provider_error, dict) and isinstance(response_value, dict):
        provider_error = response_value.get("incomplete_details")
    if not isinstance(provider_error, dict):
        provider_error = payload.get("error")
    if not isinstance(provider_error, dict) and event_type == "error":
        provider_error = payload
    fields = []
    if isinstance(provider_error, dict):
        for key in ("message", "type", "code", "reason"):
            value = provider_error.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                normalized = " ".join(str(value).split())[:MAX_LLM_ERROR_FIELD_CHARS]
                if api_key:
                    normalized = normalized.replace(api_key, "[REDACTED]")
                if normalized:
                    fields.append(f"{key}={normalized}")
    return LlmProviderError(
        f"LLM stream failed: {event_type}" + (f" ({'; '.join(fields)})" if fields else "")
    )


def _read_responses_stream(response, api_key: str) -> tuple[str, dict]:
    started = time.monotonic()
    event_name = ""
    data_lines = []
    text_parts = []
    text_bytes = 0
    stream_bytes = 0

    def process_event() -> tuple[str, dict] | None:
        nonlocal event_name, data_lines, text_bytes
        if not data_lines:
            event_name = ""
            return None
        data = "\n".join(data_lines)
        current_event = event_name
        event_name, data_lines = "", []
        if data == "[DONE]":
            raise ValueError("LLM stream ended without a response.completed event")
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError("LLM stream returned invalid event JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("LLM stream returned an invalid event object")
        event_type = payload.get("type") if isinstance(payload.get("type"), str) else current_event
        if event_type == "response.output_text.delta":
            delta = payload.get("delta")
            if not isinstance(delta, str):
                raise ValueError("LLM stream returned an invalid text delta")
            text_bytes += len(delta.encode("utf-8"))
            if text_bytes > MAX_LLM_RESPONSE_BYTES:
                raise ValueError("LLM response exceeds the 256 KB limit")
            text_parts.append(delta)
        elif event_type == "response.completed":
            completed = payload.get("response")
            if not isinstance(completed, dict):
                raise ValueError("LLM stream omitted the completed response")
            _validate_response_completion(completed, api_key, completed_event=True)
            content = "".join(text_parts) if text_parts else _responses_content(completed)
            if len(content.encode("utf-8")) > MAX_LLM_RESPONSE_BYTES:
                raise ValueError("LLM response exceeds the 256 KB limit")
            return content, _llm_usage(completed, "responses")
        elif event_type in {"response.failed", "response.incomplete", "error"}:
            raise _stream_error(event_type, payload, api_key)
        return None

    while True:
        if time.monotonic() - started > MAX_LLM_STREAM_DURATION_SECONDS:
            raise LlmTimeoutError(
                f"LLM streaming request exceeded {MAX_LLM_STREAM_DURATION_SECONDS} seconds"
            )
        raw_line = response.readline(MAX_LLM_RESPONSE_BYTES + 1)
        if time.monotonic() - started > MAX_LLM_STREAM_DURATION_SECONDS:
            raise LlmTimeoutError(
                f"LLM streaming request exceeded {MAX_LLM_STREAM_DURATION_SECONDS} seconds"
            )
        if not raw_line:
            break
        stream_bytes += len(raw_line)
        if stream_bytes > MAX_LLM_STREAM_BYTES:
            raise ValueError("LLM event stream exceeds the 4 MB transport limit")
        if len(raw_line) > MAX_LLM_RESPONSE_BYTES:
            raise ValueError("LLM stream event exceeds the 256 KB limit")
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as error:
            raise ValueError("LLM stream is not valid UTF-8") from error
        if not line:
            result = process_event()
            if result is not None:
                return result
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    result = process_event()
    if result is not None:
        return result
    raise ValueError("LLM stream ended without a response.completed event")


def _is_event_stream(response) -> bool:
    headers = getattr(response, "headers", None)
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    return str(content_type).partition(";")[0].strip().casefold() == "text/event-stream"


def _validate_response_completion(value: dict, api_key: str, *, completed_event: bool = False) -> None:
    status = value.get("status")
    if (value.get("error") is not None or value.get("incomplete_details") is not None
            or (status != "completed" and not (completed_event and status is None))):
        raise _stream_error("response.not_completed", {"response": value}, api_key)


def _call_llm(config: dict, api_key: str, instruction: str, payload: object) -> tuple[str, dict]:
    user_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if config["wireApi"] == "responses":
        request_payload = {
            "model": config["model"],
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": instruction}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
            ],
        }
    else:
        request_payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text},
            ],
        }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    request = urllib.request.Request(
        _llm_request_url(config),
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config["timeoutSeconds"]) as response:
            if config["wireApi"] == "responses" and _is_event_stream(response):
                return _read_responses_stream(response, api_key)
            response_value = _read_json_response(response)
    except urllib.error.HTTPError as error:
        raise LlmProviderError(_llm_http_error(error, api_key)) from error
    except (TimeoutError, socket.timeout) as error:
        raise LlmTimeoutError(
            f"LLM request timed out after {config['timeoutSeconds']} seconds"
        ) from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise LlmTimeoutError(
                f"LLM request timed out after {config['timeoutSeconds']} seconds"
            ) from error
        raise LlmTransportError(
            f"LLM network request failed: {type(error.reason).__name__}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError("LLM returned an invalid JSON response") from error
    except UnicodeDecodeError as error:
        raise ValueError("LLM response is not valid UTF-8") from error
    if config["wireApi"] == "responses":
        content = _responses_content(response_value)
        _validate_response_completion(response_value, api_key)
    else:
        choices = response_value.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("LLM returned invalid Chat Completions choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM returned invalid Chat Completions message")
        if response_value.get("error") is not None or choices[0].get("finish_reason") != "stop" or message.get("refusal"):
            raise ValueError("LLM Chat Completions response did not finish successfully")
        content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned empty content")
    return content, _llm_usage(response_value, config["wireApi"])


def summary_decisions(query: dict) -> dict:
    """Expose persisted generation decisions without enlarging Summary snapshots."""
    project_id = (query.get("project") or [""])[0]
    skill = (query.get("skill") or [""])[0]
    try:
        version = int((query.get("version") or [""])[0])
        page = max(int((query.get("page") or ["1"])[0]), 1)
        page_size = min(max(int((query.get("limit") or ["20"])[0]), 1), 100)
    except (TypeError, ValueError) as error:
        raise ValueError("valid Summary version, page and limit required") from error
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None or not skill or version < 1:
        raise ValueError("registered project, Skill and version required")
    database = _database_for_skill(project, skill)
    if not database.is_file():
        raise ValueError("project database is unavailable")
    connection = connect_database(database, timeout=5)
    try:
        connection.execute("BEGIN")
        summary = connection.execute(
            "SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
            (project_id, skill, version),
        ).fetchone()
        if summary is None:
            raise ValueError("summary version not found")
        jobs = connection.execute(
            "SELECT id FROM summary_generation_jobs WHERE summary_id = ? "
            "AND project_id = ? AND skill = ? AND status = 'SUCCEEDED'",
            (summary["id"], project_id, skill),
        ).fetchall()
        if len(jobs) != 1:
            raise ValueError("Summary has no unique successful generation job")
        sources = {row[0] for row in connection.execute(
            "SELECT record_id FROM summary_generation_sources WHERE job_id = ?", (jobs[0]["id"],),
        )}
        candidates: dict[str, list[str]] = {}
        decisions = []
        for batch in connection.execute(
            "SELECT phase, level, batch_index, result_json FROM summary_generation_batches "
            "WHERE job_id = ? AND status = 'SUCCEEDED' "
            "ORDER BY CASE phase WHEN 'MAP' THEN 0 WHEN 'REDUCE' THEN 1 ELSE 2 END, level, batch_index",
            (jobs[0]["id"],),
        ):
            result = decode_json(batch["result_json"])
            if not isinstance(result, dict):
                raise ValueError("generation decisions are unavailable")
            phase = batch["phase"]
            for item in result.get("recordDecisions" if phase == "MAP" else "decisions", []):
                identity = item.get("recordId") if phase == "MAP" else item.get("candidateId")
                source_ids = [identity] if phase == "MAP" else candidates.get(identity)
                if source_ids is None or not set(source_ids).issubset(sources):
                    raise ValueError("generation decision source lineage is unavailable")
                decisions.append({
                    "phase": phase, "level": batch["level"], "batchIndex": batch["batch_index"],
                    "inputId": identity, "decision": item.get("decision"), "reason": item.get("reason"),
                    "sourceRecordIds": source_ids,
                })
            for candidate in result.get("candidates", []):
                source_ids = candidate.get("sourceRecordIds")
                if not isinstance(source_ids, list) or not set(source_ids).issubset(sources):
                    raise ValueError("generation candidate source lineage is unavailable")
                candidates[candidate["id"]] = source_ids
        total = len(decisions)
        offset = (page - 1) * page_size
        return {"decisions": decisions[offset:offset + page_size], "page": page,
                "pageSize": page_size, "total": total, "hasMore": page * page_size < total}
    finally:
        connection.close()


def summary_evidence(query: dict) -> dict:
    project_id = query.get("project", [""])[0]
    skill = query.get("skill", [""])[0]
    try:
        version = int(query.get("version", [""])[0])
    except ValueError as error:
        raise ValueError("valid Summary version required") from error
    try:
        page = max(int(query.get("page", ["1"])[0]), 1)
        page_size = min(max(int(query.get("limit", ["20"])[0]), 1), 100)
    except ValueError as error:
        raise ValueError("valid evidence page and limit required") from error
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None or not skill or version < 1:
        raise ValueError("registered project, Skill and version required")
    database = _database_for_skill(project, skill)
    if not database.is_file():
        raise ValueError("project database is unavailable")
    connection = connect_database(database, timeout=5)
    try:
        row = connection.execute(
            "SELECT id, summary_json FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
            (project_id, skill, version),
        ).fetchone()
        if row is None:
            raise ValueError("summary version not found")
        summary = decode_json(row["summary_json"])
        rules = summary.get("rules", []) if isinstance(summary, dict) else []
        if isinstance(summary, dict) and summary.get("format") == "forge-skill-training-summary-v6":
            total = int(connection.execute(
                """SELECT COUNT(*) FROM learning_records AS records
                   JOIN learning_summary_sources AS sources ON sources.record_id = records.id
                   WHERE sources.summary_id = ? AND records.project_id = ? AND records.skill = ?""",
                (row["id"], project_id, skill),
            ).fetchone()[0])
            source_rows = connection.execute(
                """SELECT records.id, records.run_id, records.captured_at, records.output_json,
                          records.edited_content, records.review_note, records.is_classic
                   FROM learning_records AS records
                   JOIN learning_summary_sources AS sources ON sources.record_id = records.id
                   WHERE sources.summary_id = ? AND records.project_id = ? AND records.skill = ?
                   ORDER BY records.captured_at, records.id LIMIT ? OFFSET ?""",
                (row["id"], project_id, skill, page_size, (page - 1) * page_size),
            ).fetchall()
            rule_ids_by_record: dict[str, list[str]] = {}
            record_ids = [source["id"] for source in source_rows]
            if record_ids:
                placeholders = ",".join("?" for _ in record_ids)
                for source in connection.execute(
                    "SELECT rule_id, record_id FROM learning_summary_rule_sources "
                    f"WHERE summary_id = ? AND record_id IN ({placeholders}) "
                    "ORDER BY rule_id, record_id",
                    (row["id"], *record_ids),
                ).fetchall():
                    rule_ids_by_record.setdefault(source["record_id"], []).append(source["rule_id"])
            records = []
            for source in source_rows:
                raw = source["edited_content"] or source["output_json"]
                try:
                    content = json.loads(raw)
                except (TypeError, ValueError):
                    content = raw
                records.append({
                    "recordId": source["id"],
                    "runId": source["run_id"],
                    "capturedAt": source["captured_at"],
                    "reviewNote": source["review_note"],
                    "classic": bool(source["is_classic"]),
                    "effectiveContent": content,
                    "ruleIds": rule_ids_by_record.get(source["id"], []),
                })
            return {
                "records": records, "page": page, "pageSize": page_size, "total": total,
                "hasMore": page * page_size < total,
            }
        decisions = summary.get("candidateDecisions", []) if isinstance(summary, dict) else []
        packet = evidence_packet(connection, row["id"], project_id, skill, [*rules, *decisions])
        return {
            "records": packet["records"], "page": 1,
            "pageSize": len(packet["records"]), "total": len(packet["records"]),
            "hasMore": False,
        }
    finally:
        connection.close()


def _write_registry(path: Path, value: dict) -> None:
    temporary = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _registered_project_path_available(project: dict) -> bool:
    value = project.get("path")
    return isinstance(value, str) and bool(value.strip()) and Path(value).is_dir()


def projects() -> list[dict]:
    registry_path = REGISTRY_PATH if REGISTRY_PATH.is_file() else LEGACY_REGISTRY_PATH
    with _PROJECT_REGISTRY_LOCK:
        with _registry_file_lock(registry_path):
            try:
                value = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
            if not isinstance(value, dict):
                return []
            project_items = value.get("projects", [])
            if not isinstance(project_items, list):
                return []
            result = []
            changed = False
            for item in project_items:
                if not isinstance(item, dict):
                    continue
                project = dict(item)
                project["projectId"] = project.get("projectId", project.get("id"))
                if not _project_databases(project):
                    continue
                configured = project.get("status")
                if configured not in {"CONFLICT", "DISABLED"}:
                    databases = _project_databases(project)
                    path_available = _registered_project_path_available(project)
                    database_available = any(database.is_file() for database in databases)
                    status = "ACTIVE" if path_available and database_available else "UNAVAILABLE"
                    updates = {"status": status}
                    if status == "ACTIVE":
                        updates.update({"unavailableSince": None, "healthReason": None})
                    else:
                        updates.update({
                            "unavailableSince": item.get("unavailableSince") or now(),
                            "healthReason": (
                                "project path unavailable" if not path_available
                                else "learning database unavailable"
                            ),
                        })
                    for key, value_item in updates.items():
                        if item.get(key) != value_item:
                            item[key] = value_item
                            changed = True
                    project.update(updates)
                result.append(project)
            if changed:
                _write_registry(registry_path, value)
            return result


def set_project_registration_status(payload: dict) -> dict:
    project_id = payload.get("projectId")
    action = payload.get("action")
    if not isinstance(project_id, str) or action not in {"ARCHIVE", "RESTORE"}:
        raise ValueError("projectId and ARCHIVE or RESTORE action are required")
    registry_path = REGISTRY_PATH if REGISTRY_PATH.is_file() else LEGACY_REGISTRY_PATH
    with _PROJECT_REGISTRY_LOCK:
        with _registry_file_lock(registry_path):
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("project registry is unavailable") from error
            entries = registry.get("projects") if isinstance(registry, dict) else None
            if not isinstance(entries, list):
                raise ValueError("project registry is invalid")
            matches = [item for item in entries if isinstance(item, dict)
                       and item.get("projectId", item.get("id")) == project_id]
            if not matches:
                raise ValueError("project not found")
            if len(matches) != 1 or matches[0].get("status") == "CONFLICT":
                raise ValueError("conflicting project identity must be resolved before changing status")
            entry = matches[0]
            timestamp = now()
            if action == "ARCHIVE":
                entry.update({
                    "status": "DISABLED", "disabledAt": timestamp,
                    "unavailableSince": None, "healthReason": "archived by operator",
                })
            else:
                path_available = _registered_project_path_available(entry)
                database_available = any(path.is_file() for path in _project_databases(entry))
                available = path_available and database_available
                entry.update({
                    "status": "ACTIVE" if available else "UNAVAILABLE",
                    "disabledAt": None,
                    "unavailableSince": None if available else timestamp,
                    "healthReason": None if available else (
                        "project path unavailable" if not path_available
                        else "learning database unavailable"
                    ),
                })
            _write_registry(registry_path, registry)
            return {
                "projectId": project_id, "status": entry["status"],
                "disabledAt": entry.get("disabledAt"),
                "unavailableSince": entry.get("unavailableSince"),
                "healthReason": entry.get("healthReason"),
            }


def hook_status() -> dict:
    return global_hook_status(FORGE_ROOT)


def update_global_hook(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Hook configuration must be a JSON object")
    action = payload.get("action")
    host = payload.get("host")
    if host not in {"codex", "claude-code", "cursor"}:
        raise ValueError("host must be codex, claude-code, or cursor")
    if action == "REMOVE":
        return remove_global_hook(FORGE_ROOT, host)
    if action == "CONFIGURE":
        return configure_global_hook(FORGE_ROOT, host)
    raise ValueError("action must be CONFIGURE or REMOVE")


def decode_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _project_matches_scan(project: dict, project_filter: str) -> bool:
    """Exclude archived projects from broad scans while allowing explicit inspection."""
    if project_filter:
        return project.get("projectId") == project_filter
    return project.get("status") != "DISABLED"


def _record_query_options(query: dict[str, list[str]]) -> tuple[str, str, str, str, str, list[str]]:
    project_filter = query.get("project", [""])[0]
    skill_filter = query.get("skill", [""])[0]
    status_filter = query.get("status", [""])[0]
    search = query.get("q", [""])[0].strip()
    clauses, values = [], []
    if skill_filter:
        clauses.append("skill = ?")
        values.append(skill_filter)
    if status_filter:
        clauses.append("review_status = ?")
        values.append(status_filter)
    if search:
        clauses.append(
            "(output_json LIKE ? OR host_output_json LIKE ? OR edited_content LIKE ? "
            "OR review_note LIKE ? OR run_id LIKE ?)"
        )
        values.extend([f"%{search}%"] * 5)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return project_filter, skill_filter, status_filter, search, where, values


def _query_record_snapshot(
    query: dict[str, list[str]], project_items: list[dict], *, limit: int, offset: int,
    include_total: bool, collapse_shared_hooks: bool = False,
) -> tuple[list[dict], int | None]:
    project_filter, skill_filter, _status_filter, _search, where, values = _record_query_options(query)
    records = []
    total = 0 if include_total else None
    fetch_limit = limit + offset
    targets = [
        (project, database)
        for project in project_items if _project_matches_scan(project, project_filter)
        for database in ([_database_for_skill(project, skill_filter)] if skill_filter else _project_databases(project))
        if database.is_file()
    ]
    single_database = len(targets) == 1
    shared_counts: dict[tuple[str, str], int] = {}
    for project in project_items:
        if not _project_matches_scan(project, project_filter):
            continue
        databases = [_database_for_skill(project, skill_filter)] if skill_filter else _project_databases(project)
        for database in databases:
            if not database.is_file():
                continue
            try:
                connection = connect_database(database, timeout=5)
                try:
                    connection.row_factory = sqlite3.Row
                    connection.execute("BEGIN")
                    if collapse_shared_hooks:
                        shared_rows = connection.execute(
                            "SELECT project_id, shared_capture_id, COUNT(*) AS member_count "
                            "FROM learning_records" + where
                            + (" AND " if where else " WHERE ")
                            + "capture_source = 'HOST_HOOK' "
                            + "AND shared_capture_id IS NOT NULL "
                            + "GROUP BY project_id, shared_capture_id",
                            values,
                        ).fetchall()
                        for shared_row in shared_rows:
                            key = (shared_row["project_id"], shared_row["shared_capture_id"])
                            shared_counts[key] = (
                                shared_counts.get(key, 0) + int(shared_row["member_count"])
                            )
                    if include_total:
                        total += int(connection.execute(
                            "SELECT COUNT(*) FROM learning_records" + where, values,
                        ).fetchone()[0])
                    rows = connection.execute(
                        "SELECT * FROM learning_records" + where
                        + " ORDER BY captured_at DESC, id DESC LIMIT ? OFFSET ?",
                        (
                            *values,
                            fetch_limit if shared_counts or not single_database else limit,
                            0 if shared_counts or not single_database else offset,
                        ),
                    ).fetchall()
                finally:
                    connection.close()
            except sqlite3.DatabaseError:
                _warnings().append({
                    "projectId": project.get("projectId"), "path": project.get("path"),
                    "error": "database unavailable",
                })
                continue
            for row in rows:
                item = dict(row)
                item["shared_capture_pending"] = bool(item.get("shared_capture_id")) and not bool(
                    item.get("shared_capture_complete")
                )
                for field in (
                    "output_json", "host_output_json", "diagnostics_json",
                    "metadata_json", "evaluation_json",
                ):
                    item[field.removesuffix("_json")] = decode_json(item.pop(field))
                records.append(item)
    records.sort(key=lambda item: (item["captured_at"], item["id"], item["project_id"], item["skill"]), reverse=True)
    if collapse_shared_hooks:
        if not shared_counts:
            return (
                records[:limit] if single_database else records[offset:offset + limit],
                total,
            )
        records = _collapse_shared_hook_records(records)
        page = records[offset:offset + limit]
        _enrich_shared_hook_records(page, project_items)
        collapsed_total = (
            total - sum(count - 1 for count in shared_counts.values())
            if include_total and total is not None else None
        )
        return page, collapsed_total
    return records[:limit] if single_database else records[offset:offset + limit], total


def _hook_capture_metadata(record: dict) -> dict:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = decode_json(record.get("metadata_json"))
    capture = metadata.get("hookCapture") if isinstance(metadata, dict) else None
    return capture if isinstance(capture, dict) else {}


def _shared_hook_capture_id(record: dict) -> str | None:
    if record.get("capture_source") != "HOST_HOOK":
        return None
    stored = record.get("shared_capture_id")
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    capture = _hook_capture_metadata(record)
    value = capture.get("sharedCaptureId")
    if capture.get("attribution") != "SHARED_HOST_TURN":
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _collapse_shared_hook_records(records: list[dict]) -> list[dict]:
    result = []
    groups: dict[tuple[str, str], dict] = {}
    for record in records:
        shared_id = _shared_hook_capture_id(record)
        if shared_id is None:
            result.append(record)
            continue
        key = (record["project_id"], shared_id)
        representative = groups.get(key)
        if representative is None:
            representative = dict(record)
            representative["shared_capture_id"] = shared_id
            representative["shared_review_group_id"] = shared_id
            representative["shared_record_ids"] = []
            representative["shared_skills"] = []
            groups[key] = representative
            result.append(representative)
        representative["shared_record_ids"].append(record["id"])
        representative["shared_skills"].append(record["skill"])
    for record in groups.values():
        record["shared_skills"] = sorted(set(record["shared_skills"]))
        record["shared_record_count"] = len(record["shared_record_ids"])
    return result


def _enrich_shared_hook_records(records: list[dict], project_items: list[dict]) -> None:
    requested: dict[str, set[str]] = {}
    representatives: dict[tuple[str, str], dict] = {}
    for record in records:
        shared_id = record.get("shared_review_group_id")
        project_id = record.get("project_id")
        if isinstance(shared_id, str) and isinstance(project_id, str):
            requested.setdefault(project_id, set()).add(shared_id)
            representatives[(project_id, shared_id)] = record
    if not requested:
        return
    members: dict[tuple[str, str], list[tuple[str, str, bool]]] = {}
    for project in project_items:
        project_id = project.get("projectId")
        shared_ids = requested.get(project_id)
        if not shared_ids:
            continue
        placeholders = ",".join("?" for _item in shared_ids)
        for database in _project_databases(project):
            if not database.is_file():
                continue
            try:
                connection = connect_database(database, timeout=5)
                try:
                    rows = connection.execute(
                        "SELECT id, skill, shared_capture_id, shared_capture_complete "
                        "FROM learning_records "
                        "WHERE project_id = ? AND capture_source = 'HOST_HOOK' "
                        f"AND shared_capture_id IN ({placeholders})",
                        (project_id, *sorted(shared_ids)),
                    ).fetchall()
                finally:
                    connection.close()
            except sqlite3.DatabaseError:
                _warnings().append({
                    "projectId": project_id, "path": project.get("path"),
                    "error": "database unavailable",
                })
                continue
            for row in rows:
                members.setdefault((project_id, row["shared_capture_id"]), []).append(
                    (row["id"], row["skill"], bool(row["shared_capture_complete"]))
                )
    for key, representative in representatives.items():
        group = members.get(key, [])
        representative["shared_record_ids"] = [record_id for record_id, _skill, _complete in group]
        representative["shared_skills"] = sorted({skill for _record_id, skill, _complete in group})
        representative["shared_record_count"] = len(group)
        representative["shared_capture_pending"] = any(
            not complete for _record_id, _skill, complete in group
        ) or bool(representative.get("shared_capture_pending"))
        if len(group) <= 1 and not representative["shared_capture_pending"]:
            representative["shared_review_group_id"] = None


def query_records(
    query: dict[str, list[str]], *, project_items: list[dict] | None = None,
) -> list[dict]:
    _warnings().clear()
    try:
        limit = min(max(int(query.get("limit", ["200"])[0]), 1), 1000)
    except ValueError:
        limit = 200
    try:
        offset = max(int(query.get("offset", ["0"])[0]), 0)
    except ValueError:
        offset = 0
    records, _total = _query_record_snapshot(
        query, project_items if project_items is not None else projects(),
        limit=limit, offset=offset, include_total=False,
    )
    return records


def query_record_page(query: dict[str, list[str]]) -> dict:
    """Return one small server-side page without requiring the browser to load all records."""
    try:
        page = max(int(query.get("page", ["1"])[0]), 1)
    except ValueError:
        page = 1
    page_size = 20
    base = {key: value for key, value in query.items() if key not in {"page", "limit", "offset"}}
    base["limit"] = [str(page_size)]
    base["offset"] = [str((page - 1) * page_size)]
    project_items = projects()
    _warnings().clear()
    items, total = _query_record_snapshot(
        base, project_items, limit=page_size, offset=(page - 1) * page_size,
        include_total=True, collapse_shared_hooks=True,
    )
    assert total is not None
    return {
        "items": items, "page": page, "pageSize": page_size, "total": total,
        "hasMore": page * page_size < total, "projects": project_items,
    }


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
        if not _project_matches_scan(project, project_id):
            continue
        databases = [_database_for_skill(project, skill)] if skill else _project_databases(project)
        for database in databases:
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


def _database_for_skill(project: dict, skill: str) -> Path:
    databases = project.get("databases")
    if isinstance(databases, dict) and isinstance(databases.get(skill), str):
        return Path(databases[skill])
    return Path(str(project.get("database", "")))


def _normalize_skill(skill: str) -> str:
    return skill.strip().removeprefix("skill.").replace("_", "-")


def _skill_text(skill: str) -> str:
    path = SKILL_ROOT.parent / skill / "SKILL.md"
    if not path.is_file():
        raise ValueError("Skill definition is unavailable")
    return path.read_text(encoding="utf-8")


def _summary_generation_scope(
    project_id: object, skill_value: object, *, require_enabled: bool = True,
) -> tuple[dict, Path, str]:
    if not isinstance(project_id, str) or not isinstance(skill_value, str) or not skill_value.strip():
        raise ValueError("projectId and skill are required")
    skill = _normalize_skill(skill_value)
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    if require_enabled and skill not in _enabled_skills(project):
        raise ValueError("skill is not enabled for learning in this project")
    database = _database_for_skill(project, skill)
    if not database.is_file():
        raise ValueError("project database is unavailable")
    return project, database, skill


def _summary_provider_identity(config: dict) -> str:
    request_url = _llm_request_url(config)
    return "sha256:" + hashlib.sha256(
        f"{config['wireApi']}:{request_url}".encode("utf-8")
    ).hexdigest()


def _summary_llm() -> tuple[dict, object]:
    config, api_key = _configured_llm()

    def call_llm(instruction: str, payload: object) -> tuple[str, dict]:
        return _call_llm(config, api_key, instruction, payload)

    return config, call_llm


def start_summary_generation(payload: dict) -> dict:
    return _submit_summary_request(payload, "GENERATE", _start_summary_generation)


def _submit_summary_request(payload: dict, action: str, create) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Summary generation request must be a JSON object")
    if "submissionId" not in payload:
        return create(payload)
    project_id = payload.get("projectId")
    _project, database, skill = _summary_generation_scope(project_id, payload.get("skill"))
    request = {
        "action": action, "projectId": project_id, "skill": skill,
        "jobId": payload.get("jobId") if action == "RETRY" else None,
        "windowMonths": payload.get("windowMonths", 6) if action == "GENERATE" else None,
        "language": payload.get("language", "zh-CN") if action == "GENERATE" else None,
    }
    return run_summary_submission(
        database, submission_id=payload["submissionId"], project_id=project_id,
        skill=skill, request=request, create=lambda: create(payload),
    )


def _start_summary_generation(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Summary generation request must be a JSON object")
    project_id = payload.get("projectId")
    _project, database, skill = _summary_generation_scope(project_id, payload.get("skill"))
    window_months = payload.get("windowMonths", 6)
    if not isinstance(window_months, int) or isinstance(window_months, bool):
        raise ValueError("windowMonths must be an integer")
    language = payload.get("language", "zh-CN")
    if language not in {"zh-CN", "en"}:
        raise ValueError("language must be zh-CN or en")
    config, call_llm = _summary_llm()
    return start_summary_job(
        database, project_id=project_id, skill=skill, skill_text=_skill_text(skill),
        model=config["model"], call_llm=call_llm, window_months=window_months,
        language=language,
        provider_identity=_summary_provider_identity(config),
        **({"submission_id": payload["submissionId"]} if "submissionId" in payload else {}),
    )


def get_summary_generation_estimate(query: dict[str, list[str]]) -> dict:
    project_id = (query.get("project") or [""])[0]
    skill_value = (query.get("skill") or [""])[0]
    _project, database, skill = _summary_generation_scope(project_id, skill_value)
    language = (query.get("language") or ["zh-CN"])[0]
    try:
        window_months = int((query.get("windowMonths") or ["6"])[0])
    except (TypeError, ValueError) as error:
        raise ValueError("windowMonths must be an integer") from error
    return estimate_summary_generation(
        database, project_id=project_id, skill=skill, skill_text=_skill_text(skill),
        window_months=window_months, language=language,
    )


class SummaryJobNotFound(ValueError):
    """An absent job is distinct from a failed status query."""


class SummarySubmissionNotFound(ValueError):
    """A missing receipt does not settle an uncertain POST outcome."""


def get_summary_generation(query: dict[str, list[str]]) -> dict:
    project_id = (query.get("project") or [""])[0]
    skill_value = (query.get("skill") or [""])[0]
    _project, database, skill = _summary_generation_scope(
        project_id, skill_value, require_enabled=False,
    )
    job_id = (query.get("job") or [None])[0]
    submission_id = (query.get("submission") or [None])[0]
    result = summary_job_status(
        database, job_id=job_id, project_id=project_id, skill=skill,
        **({"submission_id": submission_id} if submission_id else {}),
    )
    if result is None or result["projectId"] != project_id or result["skill"] != skill:
        if submission_id:
            raise SummarySubmissionNotFound("Summary submission is not registered yet; outcome is unknown")
        raise SummaryJobNotFound("Summary generation job not found")
    return result


def retry_summary_generation(payload: dict) -> dict:
    return _submit_summary_request(payload, "RETRY", _retry_summary_generation)


def _retry_summary_generation(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Summary generation retry request must be a JSON object")
    project_id = payload.get("projectId")
    _project, database, skill = _summary_generation_scope(project_id, payload.get("skill"))
    job_id = payload.get("jobId")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("jobId is required")
    previous = summary_job_status(database, job_id=job_id)
    if previous is None or previous["projectId"] != project_id or previous["skill"] != skill:
        raise ValueError("Summary generation job not found")
    config, call_llm = _summary_llm()
    return retry_summary_job(
        database, previous_job_id=job_id, skill_text=_skill_text(skill),
        model=config["model"], call_llm=call_llm,
        provider_identity=_summary_provider_identity(config),
        **({"submission_id": payload["submissionId"]} if "submissionId" in payload else {}),
    )


def recover_summary_generation_jobs() -> int:
    interrupted = 0
    seen: set[Path] = set()
    for project in projects():
        for database in _project_databases(project):
            if database in seen or not database.is_file():
                continue
            seen.add(database)
            try:
                interrupted += interrupt_stale_jobs(database)
            except (OSError, sqlite3.Error):
                continue
    return interrupted


def _project_databases(project: dict) -> list[Path]:
    databases = project.get("databases")
    values = databases.values() if isinstance(databases, dict) else [project.get("database")]
    result = []
    for value in values:
        if isinstance(value, str):
            path = Path(value)
            if path not in result:
                result.append(path)
    return result


MAX_OVERLAY_RULES = 30
MAX_OVERLAY_CONTENT_BYTES = 20_000
SUMMARY_GENERATED_OVERLAY = "SUMMARY_GENERATED"
MANUAL_COPY_OVERLAY = "MANUAL_COPY"


class OverlayConflict(ValueError):
    def __init__(self, message: str, *, overlay_id: str, version: int, replaceable: bool):
        super().__init__(message)
        self.overlay_id = overlay_id
        self.version = version
        self.replaceable = replaceable


def _overlay_origin(manifest: object) -> str:
    if not isinstance(manifest, dict):
        return "LEGACY"
    origin = manifest.get("origin")
    if isinstance(origin, dict) and origin.get("type") in {
        SUMMARY_GENERATED_OVERLAY, MANUAL_COPY_OVERLAY,
    }:
        return origin["type"]
    if isinstance(manifest.get("sourceSummary"), dict):
        return SUMMARY_GENERATED_OVERLAY
    return "LEGACY"


def _validated_overlay_summary(
    connection: sqlite3.Connection, row: sqlite3.Row, project_id: str, skill: str,
) -> tuple[dict, list[dict]]:
    if row["lifecycle_status"] != "REVIEWED":
        raise ValueError(f"summary v{row['version']} must be REVIEWED before overlay generation")
    snapshot = decode_json(row["summary_json"])
    if (not isinstance(snapshot, dict)
            or snapshot.get("format") != "forge-skill-training-summary-v6"
            or snapshot.get("status") != "REVIEWED"
            or snapshot.get("projectId") != project_id
            or _normalize_skill(str(snapshot.get("skill", ""))) != skill
            or snapshot.get("version") != row["version"]):
        raise ValueError(f"summary v{row['version']} is not a reviewed AI Summary v6")
    generation = snapshot.get("generation")
    quality = snapshot.get("quality")
    coverage = snapshot.get("coverage")
    source_count = snapshot.get("sourceCount")
    if (not isinstance(generation, dict) or generation.get("mode") != "llm-direct"
            or not isinstance(quality, dict) or quality.get("humanReviewRequired") is not True
            or quality.get("allInputsDispositioned") is not True
            or not isinstance(coverage, dict) or coverage.get("coverageRate") != 1.0
            or coverage.get("sourceRecords") != source_count
            or coverage.get("processedRecords") != source_count
            or not isinstance(source_count, int) or isinstance(source_count, bool) or source_count < 1
            or row["source_count"] != source_count):
        raise ValueError(f"summary v{row['version']} does not satisfy the AI Summary quality gate")
    rules = snapshot.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"summary v{row['version']} rules are invalid")
    if not any(isinstance(rule, dict) and rule.get("status") == "CONFIRMED" for rule in rules):
        raise ValueError("selected Summary contains no confirmed rules")
    summary_sources = {
        item[0] for item in connection.execute(
            "SELECT record_id FROM learning_summary_sources WHERE summary_id = ?", (row["id"],),
        ).fetchall()
    }
    if len(summary_sources) != source_count:
        raise ValueError(f"summary v{row['version']} has incomplete source lineage")
    scoped_sources = {
        item[0] for item in connection.execute(
            "SELECT sources.record_id FROM learning_summary_sources AS sources "
            "JOIN learning_records AS records ON records.id = sources.record_id "
            "WHERE sources.summary_id = ? AND records.project_id = ? AND records.skill = ?",
            (row["id"], project_id, skill),
        ).fetchall()
    }
    if scoped_sources != summary_sources:
        raise ValueError(f"summary v{row['version']} source lineage is outside its scope")
    jobs = connection.execute(
        "SELECT * FROM summary_generation_jobs WHERE summary_id = ? AND status = 'SUCCEEDED'",
        (row["id"],),
    ).fetchall()
    if len(jobs) != 1:
        raise ValueError(f"summary v{row['version']} has no unique successful generation job")
    job = jobs[0]
    job_sources = {
        item[0] for item in connection.execute(
            "SELECT record_id FROM summary_generation_sources WHERE job_id = ?", (job["id"],),
        ).fetchall()
    }
    if (job_sources != summary_sources or job["source_count"] != source_count
            or job["project_id"] != project_id or _normalize_skill(job["skill"]) != skill
            or generation.get("sourceDigest") != job["source_digest"]
            or generation.get("skillDigest") != job["skill_digest"]
            or generation.get("model") != job["model"]
            or generation.get("providerIdentity", "") != job["provider_identity"]
            or generation.get("promptVersion") != job["prompt_version"]
            or generation.get("outputLanguage") != job["language"]):
        raise ValueError(f"summary v{row['version']} generation lineage does not match its job")
    final_batches = connection.execute(
        "SELECT result_json FROM summary_generation_batches "
        "WHERE job_id = ? AND phase = 'FINAL' AND status = 'SUCCEEDED'",
        (job["id"],),
    ).fetchall()
    if len(final_batches) != 1:
        raise ValueError(f"summary v{row['version']} has no unique successful FINAL generation result")
    final_result = decode_json(final_batches[0]["result_json"])
    final_rules = final_result.get("rules") if isinstance(final_result, dict) else None
    if not isinstance(final_rules, list):
        raise ValueError(f"summary v{row['version']} has an invalid FINAL generation result")
    final_rules_by_id = {
        item.get("id"): item for item in final_rules
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(final_rules_by_id) != len(final_rules):
        raise ValueError(f"summary v{row['version']} has an invalid FINAL rule contract")
    seen_rule_ids = set()
    confirmed = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError(f"summary v{row['version']} contains an invalid rule")
        rule_id = rule.get("id")
        status = rule.get("status")
        stage = rule.get("stage")
        if (not isinstance(rule_id, str) or not rule_id.strip() or rule_id in seen_rule_ids
                or status not in {"CONFIRMED", "EXCLUDED"}
                or stage not in {"PRE_CHECK", "FINAL_VALIDATION"}):
            raise ValueError(f"summary v{row['version']} contains an invalid reviewed rule")
        seen_rule_ids.add(rule_id)
        fields = {name: str(rule.get(name) or "").strip() for name in (
            "trigger", "instruction", "verification",
        )}
        if (not 1 <= len(fields["trigger"]) <= 200
                or not 1 <= len(fields["instruction"]) <= 500
                or not 1 <= len(fields["verification"]) <= 300):
            raise ValueError(f"summary v{row['version']} contains incomplete executable rule metadata")
        rule_sources = {
            item[0] for item in connection.execute(
                "SELECT record_id FROM learning_summary_rule_sources "
                "WHERE summary_id = ? AND rule_id = ?",
                (row["id"], rule_id),
            ).fetchall()
        }
        final_rule = final_rules_by_id.get(rule_id)
        final_source_ids = final_rule.get("sourceRecordIds") if isinstance(final_rule, dict) else None
        visible_source_ids = rule.get("sourceRecordIds")
        if (not isinstance(final_source_ids, list) or not final_source_ids
                or any(not isinstance(item, str) for item in final_source_ids)
                or len(set(final_source_ids)) != len(final_source_ids)
                or not isinstance(visible_source_ids, list)
                or any(not isinstance(item, str) for item in visible_source_ids)
                or len(set(visible_source_ids)) != len(visible_source_ids)):
            raise ValueError(f"summary v{row['version']} contains invalid rule lineage metadata")
        full_sources = set(final_source_ids)
        visible_sources = set(visible_source_ids)
        if (not rule_sources or rule_sources != full_sources or not full_sources <= summary_sources
                or not visible_sources <= full_sources
                or rule.get("supportCount") != len(full_sources)
                or rule.get("sourceIdsTruncated") is not (len(visible_source_ids) < len(full_sources))):
            raise ValueError(f"summary v{row['version']} contains incomplete rule lineage")
        if status == "CONFIRMED":
            confirmed.append(rule)
    if seen_rule_ids != set(final_rules_by_id):
        raise ValueError(f"summary v{row['version']} does not preserve the FINAL rule contract")
    return snapshot, confirmed


def _overlay_content(skill: str, rules: list[dict], language: str = "en") -> str:
    copy = {
        "en": {
            "title": f"Project Overlay: {skill}",
            "description": "This overlay supplements the global Skill and applies only to the current project.",
            "sections": {
                "PRE_CHECK": "Additional Pre-Review Checks",
                "FINAL_VALIDATION": "Additional Final Validation",
            },
        },
        "zh-CN": {
            "title": f"项目 Overlay：{skill}",
            "description": "此 Overlay 用于补充全局 Skill，仅适用于当前项目。",
            "sections": {
                "PRE_CHECK": "执行前附加检查",
                "FINAL_VALIDATION": "输出前附加校验",
            },
        },
    }[language]
    lines = [
        f"# {copy['title']}",
        "",
        copy["description"],
        "",
    ]
    for stage, heading in copy["sections"].items():
        stage_rules = [rule for rule in rules if rule["stage"] == stage]
        if not stage_rules:
            continue
        lines.extend([f"## {heading}", ""])
        for rule in stage_rules:
            trigger = rule.get("trigger")
            lines.append(f"- {trigger}: {rule['instruction']}" if trigger else f"- {rule['instruction']}")
            if rule.get("verification"):
                lines.append(f"  - {('Verify' if language == 'en' else '校验')}: {rule['verification']}")
            if rule.get("antiPattern"):
                lines.append(f"  - {('Avoid' if language == 'en' else '避免')}: {rule['antiPattern']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def create_overlay(payload: dict) -> dict:
    project_id = payload.get("projectId")
    skill = payload.get("skill")
    versions = payload.get("summaryVersions")
    language = payload.get("language", "en")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("projectId is required")
    if not isinstance(skill, str) or not skill.strip():
        raise ValueError("skill is required")
    if language not in {"zh-CN", "en"}:
        raise ValueError("language must be zh-CN or en")
    skill = _normalize_skill(skill)
    if (not isinstance(versions, list) or len(versions) != 1
            or isinstance(versions[0], bool) or not isinstance(versions[0], int)
            or versions[0] < 1):
        raise ValueError("summaryVersions must contain exactly one positive integer")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    if skill not in _enabled_skills(project):
        raise ValueError("skill is not enabled for learning in this project")
    database = _database_for_skill(project, skill)
    if not database.is_file():
        raise ValueError("project database is unavailable")
    version = versions[0]
    connection = connect_database(database, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, version, source_count, lifecycle_status, summary_json FROM learning_summaries "
                "WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError(f"summary version not found: {version}")
            snapshot, confirmed_rules = _validated_overlay_summary(
                connection, row, project_id, skill,
            )
            all_rules = []
            seen_rules = set()
            summary_digest = "sha256:" + hashlib.sha256(row["summary_json"].encode("utf-8")).hexdigest()
            source_items = [(row["id"], summary_digest, version)]
            for rule in confirmed_rules:
                key = (rule["stage"], " ".join(rule["instruction"].split()).casefold())
                if key in seen_rules:
                    raise ValueError("selected Summary contains duplicate confirmed rules")
                seen_rules.add(key)
                all_rules.append({
                    "stage": rule["stage"],
                    "trigger": rule["trigger"].strip(),
                    "instruction": rule["instruction"].strip(),
                    "verification": rule["verification"].strip(),
                    **({"antiPattern": rule["antiPattern"].strip()}
                       if isinstance(rule.get("antiPattern"), str) and rule["antiPattern"].strip() else {}),
                    "sourceSummaryVersion": version,
                    "sourceRuleId": rule["id"],
                })
            if len(all_rules) > MAX_OVERLAY_RULES:
                raise ValueError(f"overlay would contain {len(all_rules)} rules; maximum is {MAX_OVERLAY_RULES}")
            content = _overlay_content(skill, all_rules, language)
            if len(content.encode("utf-8")) > MAX_OVERLAY_CONTENT_BYTES:
                raise ValueError("overlay content exceeds the 20 KB quality limit")
            manifest = {
                "format": "forge-skill-project-overlay-v1",
                "projectId": project_id,
                "skill": skill,
                "origin": {"type": SUMMARY_GENERATED_OVERLAY},
                "rules": all_rules,
                "summaryVersions": [version],
                "sourceSummary": {
                    "id": row["id"], "version": version, "digest": summary_digest,
                    "format": snapshot["format"],
                },
                "executionSource": "content",
                "outputLanguage": language,
            }
            manifest_json = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
            content_digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
            replace_existing = payload.get("replaceExisting") is True
            source_ids = {summary_id for summary_id, _digest, _version in source_items}
            matching = []
            for candidate in connection.execute(
                "SELECT id, version, status, manifest_json FROM skill_overlays "
                "WHERE project_id = ? AND skill = ? ORDER BY version DESC",
                (project_id, skill),
            ).fetchall():
                if _overlay_origin(decode_json(candidate["manifest_json"])) != SUMMARY_GENERATED_OVERLAY:
                    continue
                candidate_sources = {
                    row[0] for row in connection.execute(
                        "SELECT summary_id FROM skill_overlay_sources WHERE overlay_id = ?",
                        (candidate["id"],),
                    ).fetchall()
                }
                if candidate_sources == source_ids:
                    matching.append(candidate)
            if matching:
                existing = matching[-1]
                if existing["status"] != "DRAFT":
                    raise OverlayConflict(
                        "an Overlay with the same Summary sources is already reviewed or active",
                        overlay_id=existing["id"], version=existing["version"], replaceable=False,
                    )
                if not replace_existing:
                    raise OverlayConflict(
                        "an Overlay draft with the same Summary sources already exists",
                        overlay_id=existing["id"], version=existing["version"], replaceable=True,
                    )
                overlay_id = existing["id"]
                next_version = existing["version"]
                connection.execute("DELETE FROM skill_overlay_sources WHERE overlay_id = ?", (overlay_id,))
                connection.execute(
                    "UPDATE skill_overlays SET status = 'DRAFT', content = ?, manifest_json = ?, "
                    "content_digest = ?, created_at = ?, reviewed_at = NULL, enabled_at = NULL, disabled_at = NULL "
                    "WHERE id = ?",
                    (content, manifest_json, content_digest, now(), overlay_id),
                )
            else:
                next_version = int(connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM skill_overlays WHERE project_id = ? AND skill = ?",
                    (project_id, skill),
                ).fetchone()[0]) + 1
                overlay_id = f"overlay-{uuid.uuid4()}"
                connection.execute(
                    "INSERT INTO skill_overlays "
                    "(id, project_id, skill, version, status, content, manifest_json, content_digest, created_at) "
                    "VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)",
                    (overlay_id, project_id, skill, next_version, content, manifest_json, content_digest, now()),
                )
            created_at = now()
            connection.executemany(
                "INSERT INTO skill_overlay_sources(overlay_id, summary_id, summary_digest) VALUES (?, ?, ?)",
                ((overlay_id, summary_id, digest) for summary_id, digest, _version in source_items),
            )
            return {
                "id": overlay_id, "projectId": project_id, "skill": skill,
                "version": next_version, "status": "DRAFT", "content": content,
                "manifest": manifest, "sourceVersions": [version],
            }
    finally:
        connection.close()


def query_overlays(query: dict[str, list[str]]) -> list[dict]:
    project_id = query.get("project", [""])[0]
    skill = query.get("skill", [""])[0]
    if skill:
        skill = _normalize_skill(skill)
    result = []
    readiness_by_skill: dict[str, dict] = {}
    for project in projects():
        if not _project_matches_scan(project, project_id):
            continue
        databases = [_database_for_skill(project, skill)] if skill else _project_databases(project)
        for database in databases:
            if not database.is_file():
                continue
            try:
                connection = connect_database(database, timeout=5)
                connection.row_factory = sqlite3.Row
                try:
                    clauses, values = [], []
                    if project_id:
                        clauses.append("project_id = ?")
                        values.append(project_id)
                    if skill:
                        clauses.append("skill = ?")
                        values.append(skill)
                    where = " WHERE " + " AND ".join(clauses) if clauses else ""
                    rows = connection.execute(
                        "SELECT * FROM skill_overlays" + where + " ORDER BY skill, version DESC", values
                    ).fetchall()
                    sources_by_overlay = {}
                    for source in connection.execute(
                        "SELECT s.overlay_id, s.summary_id FROM skill_overlay_sources s "
                        "JOIN (SELECT id FROM skill_overlays" + where + ") o "
                        "ON o.id = s.overlay_id ORDER BY s.summary_id", values
                    ):
                        sources_by_overlay.setdefault(source[0], []).append(source[1])
                    for row in rows:
                        item = dict(row)
                        item["manifest"] = decode_json(item.pop("manifest_json"))
                        item["evaluation"] = decode_json(item.pop("evaluation_json"))
                        item["sourceSummaryIds"] = sources_by_overlay.get(item["id"], [])
                        if item["skill"] not in readiness_by_skill:
                            readiness_by_skill[item["skill"]] = evaluation_readiness(FORGE_ROOT, item["skill"])
                        item["evaluationReadiness"] = readiness_by_skill[item["skill"]]
                        result.append(item)
                finally:
                    connection.close()
            except sqlite3.DatabaseError:
                _warnings().append({"projectId": project.get("projectId"), "path": project.get("path"), "error": "database unavailable"})
    return result


def _overlay_database(payload: dict) -> tuple[dict, Path, sqlite3.Connection]:
    project_id = payload.get("projectId")
    skill = payload.get("skill")
    overlay_id = payload.get("overlayId")
    if not all(isinstance(value, str) and value.strip() for value in (project_id, skill, overlay_id)):
        raise ValueError("projectId, skill and overlayId are required")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    normalized_skill = _normalize_skill(skill)
    database = _database_for_skill(project, normalized_skill)
    if not database.is_file():
        raise ValueError("project database is unavailable")
    connection = connect_database(database, timeout=5)
    return project, database, connection


def copy_overlay(payload: dict) -> dict:
    _project, _database, connection = _overlay_database(payload)
    skill = _normalize_skill(payload["skill"])
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            source = connection.execute(
                "SELECT * FROM skill_overlays WHERE id = ? AND project_id = ? AND skill = ?",
                (payload["overlayId"], payload["projectId"], skill),
            ).fetchone()
            if source is None:
                raise ValueError("overlay not found")
            manifest = decode_json(source["manifest_json"])
            if not isinstance(manifest, dict):
                raise ValueError("overlay manifest is invalid")
            next_version = int(connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM skill_overlays "
                "WHERE project_id = ? AND skill = ?",
                (payload["projectId"], skill),
            ).fetchone()[0]) + 1
            overlay_id = f"overlay-{uuid.uuid4()}"
            copied_at = now()
            manifest["origin"] = {
                "type": MANUAL_COPY_OVERLAY,
                "sourceOverlay": {
                    "id": source["id"],
                    "version": source["version"],
                    "contentDigest": source["content_digest"],
                },
                "copiedAt": copied_at,
            }
            manifest.pop("contentEdited", None)
            manifest.pop("editedAt", None)
            manifest["contentDigest"] = source["content_digest"]
            connection.execute(
                "INSERT INTO skill_overlays "
                "(id, project_id, skill, version, status, content, manifest_json, "
                "content_digest, created_at) VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)",
                (
                    overlay_id, payload["projectId"], skill, next_version, source["content"],
                    json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                    source["content_digest"], copied_at,
                ),
            )
            source_rows = connection.execute(
                "SELECT summary_id, summary_digest FROM skill_overlay_sources WHERE overlay_id = ?",
                (source["id"],),
            ).fetchall()
            connection.executemany(
                "INSERT INTO skill_overlay_sources (overlay_id, summary_id, summary_digest) "
                "VALUES (?, ?, ?)",
                ((overlay_id, row["summary_id"], row["summary_digest"]) for row in source_rows),
            )
            return {
                "id": overlay_id,
                "projectId": payload["projectId"],
                "skill": skill,
                "version": next_version,
                "status": "DRAFT",
                "origin": MANUAL_COPY_OVERLAY,
                "sourceOverlayId": source["id"],
            }
    finally:
        connection.close()


def review_overlay(payload: dict) -> dict:
    project, database, connection = _overlay_database(payload)
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > MAX_OVERLAY_CONTENT_BYTES:
        connection.close()
        raise ValueError("overlay content must be non-empty and at most 20 KB")
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, project_id, skill, status, content, manifest_json, published_at "
                "FROM skill_overlays WHERE id = ? AND project_id = ? AND skill = ?",
                (payload["overlayId"], payload["projectId"], _normalize_skill(payload["skill"])),
            ).fetchone()
            if row is None:
                raise ValueError("overlay not found")
            if row["status"] not in {"DRAFT", "REVIEWED"}:
                raise ValueError("only DRAFT or REVIEWED overlays can be edited")
            if row["published_at"]:
                raise ValueError("published overlay must be replaced by a new version")
            manifest = decode_json(row["manifest_json"])
            if not isinstance(manifest, dict):
                raise ValueError("overlay manifest is invalid")
            origin = _overlay_origin(manifest)
            if origin == SUMMARY_GENERATED_OVERLAY and content != row["content"]:
                raise ValueError("Summary-generated Overlay content is read-only; copy it before editing")
            if origin not in {SUMMARY_GENERATED_OVERLAY, MANUAL_COPY_OVERLAY}:
                raise ValueError("legacy Overlay must be copied before editing or review")
            manifest["executionSource"] = "content"
            manifest["contentDigest"] = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
            if origin == MANUAL_COPY_OVERLAY:
                manifest["contentEdited"] = content != row["content"] or manifest.get("contentEdited") is True
                if manifest["contentEdited"]:
                    manifest["editedAt"] = now()
            manifest_json = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
            digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
            connection.execute(
                "UPDATE skill_overlays SET content = ?, manifest_json = ?, content_digest = ?, status = 'REVIEWED', reviewed_at = ? "
                "WHERE id = ?",
                (content, manifest_json, digest, now(), payload["overlayId"]),
            )
            return {"overlayId": payload["overlayId"], "status": "REVIEWED", "contentDigest": digest}
    finally:
        connection.close()


def _structural_overlay_evaluation(connection: sqlite3.Connection, row: sqlite3.Row, skill: str) -> dict:
    checks = []
    content = row["content"] if isinstance(row["content"], str) else ""
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = decode_json(row["manifest_json"])

    def check(name: str, passed: bool, detail: str):
        checks.append({"id": name, "passed": bool(passed), "detail": detail})

    check("content_present", bool(content.strip()), "content is non-empty")
    check("content_size", len(content.encode("utf-8")) <= MAX_OVERLAY_CONTENT_BYTES, "content is within 20 KB")
    check("content_digest", digest == row["content_digest"], "content digest matches stored digest")
    check("manifest_valid", isinstance(manifest, dict), "manifest is valid JSON")
    if isinstance(manifest, dict):
        origin = _overlay_origin(manifest)
        origin_value = manifest.get("origin")
        origin_ok = origin in {SUMMARY_GENERATED_OVERLAY, MANUAL_COPY_OVERLAY}
        if origin == MANUAL_COPY_OVERLAY:
            source_overlay = origin_value.get("sourceOverlay") if isinstance(origin_value, dict) else None
            origin_ok = bool(
                isinstance(source_overlay, dict)
                and isinstance(source_overlay.get("id"), str) and source_overlay["id"].strip()
                and isinstance(source_overlay.get("version"), int)
                and not isinstance(source_overlay.get("version"), bool)
                and source_overlay["version"] > 0
                and isinstance(source_overlay.get("contentDigest"), str)
                and source_overlay["contentDigest"].startswith("sha256:")
            )
        check("origin", origin_ok, "overlay origin is explicit and valid")
        check("manifest_content_digest", manifest.get("contentDigest") in (None, digest), "manifest content digest matches content")
        check("execution_source", manifest.get("executionSource") == "content", "execution source is reviewed content")
        check("scope_match", manifest.get("projectId") == row["project_id"] and _normalize_skill(str(manifest.get("skill", ""))) == skill, "manifest scope matches project and Skill")
        rules = manifest.get("rules", [])
        check("rule_count", isinstance(rules, list) and 0 < len(rules) <= MAX_OVERLAY_RULES, "rule count is within the release limit")
        normalized = [" ".join(str(item.get("instruction", "")).split()).casefold() for item in rules if isinstance(item, dict)]
        check("duplicate_rules", len(normalized) == len(set(normalized)), "rules contain no duplicate instructions")
        source_rows = connection.execute(
            "SELECT summary_id, summary_digest FROM skill_overlay_sources WHERE overlay_id = ? ORDER BY summary_id",
            (row["id"],),
        ).fetchall()
        check("single_summary_source", len(source_rows) == 1, "overlay has exactly one Summary source")
        source_ok = len(source_rows) == 1
        source_summary = None
        source_snapshot = None
        if source_ok:
            source = source_rows[0]
            source_summary = connection.execute(
                "SELECT id, version, source_count, lifecycle_status, summary_json FROM learning_summaries "
                "WHERE id = ? AND project_id = ? AND skill = ?",
                (source["summary_id"], row["project_id"], skill),
            ).fetchone()
            if source_summary is not None:
                current_digest = "sha256:" + hashlib.sha256(
                    source_summary["summary_json"].encode("utf-8")
                ).hexdigest()
                source_ok = (source_summary["lifecycle_status"] == "REVIEWED"
                             and current_digest == source["summary_digest"])
                try:
                    source_snapshot, _confirmed = _validated_overlay_summary(
                        connection, source_summary, row["project_id"], skill,
                    )
                except ValueError:
                    source_ok = False
        check("source_summary", source_ok, "source is one unchanged reviewed AI Summary v6")
        manifest_source = manifest.get("sourceSummary")
        manifest_source_ok = bool(
            source_ok and isinstance(manifest_source, dict)
            and manifest_source.get("id") == source_summary["id"]
            and manifest_source.get("version") == source_summary["version"]
            and manifest_source.get("digest") == source_rows[0]["summary_digest"]
            and manifest_source.get("format") == "forge-skill-training-summary-v6"
            and manifest.get("summaryVersions") == [source_summary["version"]]
        )
        check("manifest_summary", manifest_source_ok, "manifest identifies the exact single Summary source")
        source_rules = {
            item.get("id"): item for item in (source_snapshot or {}).get("rules", [])
            if isinstance(item, dict) and item.get("status") == "CONFIRMED"
        }
        rule_lineage_ok = bool(source_rules) and isinstance(rules, list)
        seen_source_rules = set()
        for item in rules if isinstance(rules, list) else []:
            source_rule = source_rules.get(item.get("sourceRuleId")) if isinstance(item, dict) else None
            if (source_rule is None or item.get("sourceRuleId") in seen_source_rules
                    or item.get("sourceSummaryVersion") != source_summary["version"]
                    or any(item.get(field) != source_rule.get(field) for field in (
                        "stage", "trigger", "instruction", "verification",
                    ))):
                rule_lineage_ok = False
                break
            seen_source_rules.add(item["sourceRuleId"])
        rule_lineage_ok = rule_lineage_ok and seen_source_rules == set(source_rules)
        check("rule_lineage", rule_lineage_ok, "every confirmed Summary rule maps exactly once into the manifest")
        expected_content = None
        if isinstance(rules, list) and manifest.get("outputLanguage") in {"en", "zh-CN"}:
            try:
                expected_content = _overlay_content(skill, rules, manifest["outputLanguage"])
            except (KeyError, TypeError):
                expected_content = None
        deterministic_ok = (
            origin == MANUAL_COPY_OVERLAY
            or (origin == SUMMARY_GENERATED_OVERLAY and expected_content == content)
        )
        check(
            "deterministic_content", deterministic_ok,
            "Summary-generated content is canonical; manual copies are explicitly attributed",
        )
    else:
        for check_id in (
            "origin", "manifest_content_digest", "execution_source", "scope_match", "rule_count",
            "duplicate_rules", "single_summary_source", "source_summary", "manifest_summary",
            "rule_lineage", "deterministic_content",
        ):
            check(check_id, False, "manifest is unavailable")
    return {
        "format": "forge-overlay-structural-evaluation-v1",
        "evaluator": "deterministic-overlay-gate-v1",
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def _usable_active_baseline(row: sqlite3.Row, skill: str) -> bool:
    """Only use an ACTIVE overlay as a baseline if it still matches its evaluation inputs."""
    content = row["content"] if isinstance(row["content"], str) else ""
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != row["content_digest"] or not row["published_at"]:
        return False
    evaluation = decode_json(row["evaluation_json"])
    behavior = evaluation.get("behavior") if isinstance(evaluation, dict) else None
    if (not isinstance(behavior, dict) or evaluation.get("passed") is not True
            or behavior.get("passed") is not True
            or behavior.get("candidateOverlayDigest") != digest):
        return False
    skill_path = SKILL_ROOT.parent / skill / "SKILL.md"
    try:
        current_skill_digest = "sha256:" + hashlib.sha256(skill_path.read_bytes()).hexdigest()
    except OSError:
        return False
    try:
        current_corpus_digest = "sha256:" + hashlib.sha256(
            (FORGE_ROOT / "evals" / "skill-behavior-cases.json").read_bytes()
        ).hexdigest()
    except OSError:
        return False
    return (behavior.get("skillDigest") == current_skill_digest
            and behavior.get("corpusDigest") == current_corpus_digest)


def _active_baseline_snapshot(
    connection: sqlite3.Connection, project_id: str, skill: str,
) -> dict | None:
    """Return the current usable runtime baseline in one canonical shape."""
    row = connection.execute(
        "SELECT * FROM skill_overlays "
        "WHERE project_id = ? AND skill = ? AND status = 'ACTIVE'",
        (project_id, skill),
    ).fetchone()
    if row is None or not _usable_active_baseline(row, skill):
        return None
    return {
        "id": row["id"], "version": row["version"],
        "content": row["content"], "content_digest": row["content_digest"],
    }


def _write_evaluation_artifact(database: Path, overlay_id: str, version: int, artifact: dict) -> str:
    directory = database.parent / "evaluations"
    name = f"overlay-v{version}-{overlay_id}-{uuid.uuid4().hex[:8]}.json"
    destination = directory / name
    temporary = destination.with_suffix(".json.tmp")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    except OSError as error:
        raise ValueError(f"cannot persist evaluation artifact: {type(error).__name__}") from error
    return f"evaluations/{name}"


_overlay_evaluations_in_flight: set[tuple[str, str, str]] = set()
_overlay_evaluations_lock = threading.Lock()


def evaluate_and_publish_overlay(payload: dict) -> dict:
    """Reserve one Overlay evaluation across tabs served by this process."""
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(field), str) and payload[field].strip()
        for field in ("projectId", "skill", "overlayId")
    ):
        raise ValueError("projectId, skill and overlayId are required")
    key = (payload["projectId"], _normalize_skill(payload["skill"]), payload["overlayId"])
    with _overlay_evaluations_lock:
        if key in _overlay_evaluations_in_flight:
            raise ValueError("Overlay evaluation is already running")
        _overlay_evaluations_in_flight.add(key)
    try:
        return _evaluate_and_publish_overlay(payload)
    finally:
        with _overlay_evaluations_lock:
            _overlay_evaluations_in_flight.discard(key)


def _evaluate_and_publish_overlay(payload: dict) -> dict:
    """Run structural and LLM behavior gates, then publish without activating."""
    project, database, connection = _overlay_database(payload)
    skill = _normalize_skill(payload["skill"])
    force_evaluation = payload.get("forceEvaluation", False)
    if not isinstance(force_evaluation, bool):
        connection.close()
        raise ValueError("forceEvaluation must be a boolean")
    try:
        row = connection.execute(
            "SELECT * FROM skill_overlays WHERE id = ? AND project_id = ? AND skill = ?",
            (payload["overlayId"], payload["projectId"], skill),
        ).fetchone()
        if row is None:
            raise ValueError("overlay not found")
        if row["status"] != "REVIEWED":
            raise ValueError("only REVIEWED overlays can be automatically published")
        if row["published_at"]:
            raise ValueError("overlay is already published")
        structural = _structural_overlay_evaluation(connection, row, skill)
        active = _active_baseline_snapshot(connection, payload["projectId"], skill)
        snapshot = {
            "content": row["content"], "contentDigest": row["content_digest"],
            "manifestJson": row["manifest_json"], "version": row["version"],
            "activeOverlay": active,
        }
    finally:
        connection.close()

    evaluated_at = now()
    if not structural["passed"]:
        evaluation = {
            "format": "forge-overlay-release-evaluation-v2", "evaluatedAt": evaluated_at,
            "passed": False, "structural": structural, "behavior": None,
        }
        behavior_artifact = None
    else:
        try:
            config, api_key = _configured_llm()
            request_url = _llm_request_url(config)
            endpoint_digest = "sha256:" + hashlib.sha256(request_url.encode("utf-8")).hexdigest()
            behavior, behavior_artifact = evaluate_overlay(
                forge_root=FORGE_ROOT, skill_root=SKILL_ROOT,
                skill=skill, overlay_content=snapshot["content"], model=config["model"],
                output_root=database.parent / "evaluations",
                call_llm=lambda instruction, value: _call_llm(config, api_key, instruction, value),
                baseline_overlay_content=(snapshot["activeOverlay"] or {}).get("content"),
                baseline_cache_identity=f"{config['wireApi']}:{endpoint_digest}",
                force_baseline=force_evaluation,
            )
            baseline_identity = None
            if snapshot["activeOverlay"] is not None:
                baseline_identity = {
                    "id": snapshot["activeOverlay"]["id"],
                    "version": snapshot["activeOverlay"]["version"],
                    "contentDigest": snapshot["activeOverlay"]["content_digest"],
                }
            execution = {
                "wireApi": config["wireApi"], "streamRequested": False,
                "timeoutSecondsPerCall": config["timeoutSeconds"],
                "endpointDigest": endpoint_digest,
            }
            behavior["baselineOverlay"] = baseline_identity
            behavior["execution"] = execution
            behavior_artifact["baselineOverlay"] = baseline_identity
            behavior_artifact["execution"] = execution
            evaluation = {
                "format": "forge-overlay-release-evaluation-v2", "evaluatedAt": evaluated_at,
                "passed": behavior["passed"], "structural": structural, "behavior": behavior,
            }
        except ValueError as error:
            behavior_artifact = None
            evaluation = {
                "format": "forge-overlay-release-evaluation-v2", "evaluatedAt": evaluated_at,
                "passed": False, "structural": structural,
                "behavior": {"passed": False, "error": str(error)},
            }

    artifact_path = None
    connection = None
    try:
        connection = connect_database(_database_for_skill(project, skill), timeout=5)
        connection.row_factory = sqlite3.Row
        if behavior_artifact is not None:
            artifact_path = _write_evaluation_artifact(
                database, payload["overlayId"], snapshot["version"],
                {**evaluation, "behavior": behavior_artifact},
            )
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM skill_overlays "
                "WHERE id = ? AND project_id = ? AND skill = ?",
                (payload["overlayId"], payload["projectId"], skill),
            ).fetchone()
            if current is None:
                raise ValueError("overlay was deleted while evaluation was running")
            if (current["status"] != "REVIEWED" or current["content"] != snapshot["content"]
                    or current["content_digest"] != snapshot["contentDigest"]
                    or current["manifest_json"] != snapshot["manifestJson"] or current["published_at"]):
                raise ValueError("overlay changed while evaluation was running; evaluation was not published")
            active = _active_baseline_snapshot(connection, payload["projectId"], skill)
            if active != snapshot["activeOverlay"]:
                raise ValueError("active baseline changed while evaluation was running; evaluation was not published")
            current_structural = _structural_overlay_evaluation(connection, current, skill)
            if current_structural != structural:
                raise ValueError("overlay sources changed while evaluation was running; evaluation was not published")
            if artifact_path is not None:
                evaluation["artifactPath"] = artifact_path
            evaluation_json = json.dumps(evaluation, ensure_ascii=False, separators=(",", ":"))
            if not evaluation["passed"]:
                connection.execute(
                    "UPDATE skill_overlays SET evaluation_json = ?, published_at = NULL WHERE id = ?",
                    (evaluation_json, payload["overlayId"]),
                )
                return {"overlayId": payload["overlayId"], "status": "REJECTED", "evaluation": evaluation}
            published_at = now()
            connection.execute(
                "UPDATE skill_overlays SET evaluation_json = ?, published_at = ? "
                "WHERE id = ? AND status = 'REVIEWED'",
                (evaluation_json, published_at, payload["overlayId"]),
            )
            return {
                "overlayId": payload["overlayId"], "version": snapshot["version"],
                "status": "PUBLISHED", "publishedAt": published_at, "evaluation": evaluation,
            }
    except Exception:
        if artifact_path:
            try:
                (database.parent / artifact_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        if connection is not None:
            connection.close()


def activate_overlay(payload: dict) -> dict:
    project, database, connection = _overlay_database(payload)
    skill = _normalize_skill(payload["skill"])
    try:
        if skill not in _enabled_skills(project):
            raise ValueError("skill is not enabled for learning in this project")
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM skill_overlays WHERE id = ? AND project_id = ? AND skill = ?",
                (payload["overlayId"], payload["projectId"], skill),
            ).fetchone()
            if row is None:
                raise ValueError("overlay not found")
            if row["status"] != "REVIEWED":
                raise ValueError("only REVIEWED overlays can be activated")
            evaluation = decode_json(row["evaluation_json"])
            behavior = evaluation.get("behavior") if isinstance(evaluation, dict) else None
            if (not row["published_at"] or not isinstance(behavior, dict)
                    or evaluation.get("passed") is not True or behavior.get("passed") is not True
                    or behavior.get("candidateOverlayDigest") != row["content_digest"]):
                raise ValueError("overlay must pass evaluation and be published before activation")
            current_skill_path = SKILL_ROOT.parent / skill / "SKILL.md"
            current_corpus_path = FORGE_ROOT / "evals" / "skill-behavior-cases.json"
            try:
                current_skill_digest = "sha256:" + hashlib.sha256(current_skill_path.read_bytes()).hexdigest()
                current_corpus_digest = "sha256:" + hashlib.sha256(current_corpus_path.read_bytes()).hexdigest()
            except OSError as error:
                raise ValueError("evaluation inputs are unavailable; restore them, then copy this Overlay to a new version and review/evaluate it") from error
            if (behavior.get("skillDigest") != current_skill_digest
                    or behavior.get("corpusDigest") != current_corpus_digest):
                raise ValueError("Skill or evaluation corpus changed after publication; copy this Overlay to a new version and review/evaluate it")
            active = connection.execute(
                "SELECT * FROM skill_overlays "
                "WHERE project_id = ? AND skill = ? AND status = 'ACTIVE'",
                (payload["projectId"], skill),
            ).fetchone()
            if active is not None and not _usable_active_baseline(active, skill):
                active = None
            current_baseline = ({
                "id": active["id"], "version": active["version"],
                "contentDigest": active["content_digest"],
            } if active is not None else None)
            if current_baseline != behavior.get("baselineOverlay"):
                raise ValueError("active evaluation baseline changed after publication; copy this Overlay to a new version and review/evaluate it")
            structural = _structural_overlay_evaluation(connection, row, skill)
            if not structural["passed"]:
                raise ValueError("Overlay or its Summary sources changed after publication; restore its sources, then copy this Overlay to a new version and review/evaluate it")
            timestamp = now()
            connection.execute(
                "UPDATE skill_overlays SET status = 'DISABLED', disabled_at = ? "
                "WHERE project_id = ? AND skill = ? AND status = 'ACTIVE'",
                (timestamp, payload["projectId"], skill),
            )
            connection.execute(
                "UPDATE skill_overlays SET status = 'ACTIVE', enabled_at = ?, disabled_at = NULL WHERE id = ?",
                (timestamp, payload["overlayId"]),
            )
            return {"overlayId": payload["overlayId"], "status": "ACTIVE", "enabledAt": timestamp}
    finally:
        connection.close()


def disable_overlay(payload: dict) -> dict:
    _project, database, connection = _overlay_database(payload)
    try:
        with connection:
            timestamp = now()
            cursor = connection.execute(
                "UPDATE skill_overlays SET status = 'DISABLED', disabled_at = ? "
                "WHERE id = ? AND project_id = ? AND status = 'ACTIVE'",
                (timestamp, payload["overlayId"], payload["projectId"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("only an ACTIVE overlay can be disabled")
            return {"overlayId": payload["overlayId"], "status": "DISABLED", "disabledAt": timestamp}
    finally:
        connection.close()


def delete_overlay(payload: dict) -> dict:
    _project, database, connection = _overlay_database(payload)
    overlay_id = payload["overlayId"]
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM skill_overlays WHERE id = ? AND project_id = ?",
                (overlay_id, payload["projectId"]),
            ).fetchone()
            if row is None:
                raise ValueError("overlay not found")
            if row[0] == "ACTIVE":
                raise ValueError("active overlay must be disabled before deletion")
            connection.execute("DELETE FROM skill_overlay_sources WHERE overlay_id = ?", (overlay_id,))
            connection.execute("DELETE FROM skill_overlays WHERE id = ?", (overlay_id,))
        # Evaluation artifacts are deliberately outside the SQLite transaction.
        # Remove only files carrying this exact Overlay ID; a cleanup failure
        # must not turn a committed physical deletion into a false failure.
        evaluations = database.parent / "evaluations"
        if evaluations.is_dir():
            marker = f"-{overlay_id}-"
            for artifact in evaluations.iterdir():
                if artifact.is_file() and artifact.name.startswith("overlay-v") and marker in artifact.name:
                    try:
                        artifact.unlink()
                    except OSError:
                        pass
        return {"overlayId": overlay_id, "deleted": True}
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
    connection = connect_database(_database_for_skill(project, skill), timeout=5)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT summary_json, lifecycle_status FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError("summary version not found")
            if row[1] == "ARCHIVED":
                raise ValueError("an archived summary cannot be edited; create a new version")
            referenced = connection.execute(
                "SELECT 1 FROM skill_overlay_sources WHERE summary_id = "
                "(SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?)",
                (project_id, skill, version),
            ).fetchone()
            if referenced is not None:
                raise ValueError("a Summary referenced by an Overlay cannot be edited; create a new version")
            if row[1] == "REVIEWED":
                raise ValueError("a reviewed Summary is read-only; generate a new version to revise it")
            snapshot = decode_json(row[0])
            if (not isinstance(snapshot, dict)
                    or snapshot.get("format") not in {
                        "forge-skill-training-summary-v5", "forge-skill-training-summary-v6",
                    }):
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
            review_counts = {
                "pendingRules": counts["PENDING"], "confirmedRules": counts["CONFIRMED"],
                "excludedRules": counts["EXCLUDED"],
            }
            if snapshot["format"] == "forge-skill-training-summary-v5":
                statistics = snapshot.get("statistics")
                if not isinstance(statistics, dict):
                    raise ValueError("Summary statistics are invalid")
                statistics.update(review_counts)
            else:
                snapshot["review"] = review_counts
            snapshot["status"] = "REVIEWED" if counts["PENDING"] == 0 else "DRAFT"
            snapshot["reviewedAt"] = now() if snapshot["status"] == "REVIEWED" else None
            if _encoded_size(snapshot) > 20_000:
                raise ValueError("reviewed summary exceeds the 20 KB quality limit")
            connection.execute(
                "UPDATE learning_summaries SET summary_json = ?, lifecycle_status = ? "
                "WHERE project_id = ? AND skill = ? AND version = ?",
                (json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), snapshot["status"], project_id, skill, version),
            )
            return {"projectId": project_id, "skill": skill, "version": version,
                    "status": snapshot["status"],
                    "statistics": snapshot.get("statistics", review_counts)}
    finally:
        connection.close()


def delete_summary(payload: dict) -> dict:
    project_id, skill, version = payload.get("projectId"), payload.get("skill"), payload.get("version")
    if not isinstance(project_id, str) or not isinstance(skill, str) or not isinstance(version, int):
        raise ValueError("projectId, skill and integer version are required")
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        raise ValueError("project not found")
    database = _database_for_skill(project, skill)
    connection = connect_database(database, timeout=5)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT lifecycle_status FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()
            if row is None:
                raise ValueError("summary version not found")
            if row[0] == "ARCHIVED":
                raise ValueError("cannot delete an archived summary; preserve it for Overlay traceability")
            summary_id = connection.execute(
                "SELECT id FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            ).fetchone()[0]
            if connection.execute(
                "SELECT 1 FROM skill_overlay_sources WHERE summary_id = ?", (summary_id,)
            ).fetchone() is not None:
                raise ValueError("cannot delete a Summary referenced by an Overlay")
            job_ids = [item[0] for item in connection.execute(
                "SELECT id FROM summary_generation_jobs WHERE summary_id = ?", (summary_id,),
            ).fetchall()]
            if job_ids:
                placeholders = ",".join("?" for _ in job_ids)
                connection.execute(
                    f"DELETE FROM summary_generation_batches WHERE job_id IN ({placeholders})", job_ids,
                )
                connection.execute(
                    f"DELETE FROM summary_generation_sources WHERE job_id IN ({placeholders})", job_ids,
                )
                connection.execute(
                    f"DELETE FROM summary_generation_jobs WHERE id IN ({placeholders})", job_ids,
                )
            connection.execute("DELETE FROM learning_summary_sources WHERE summary_id = ?", (summary_id,))
            connection.execute("DELETE FROM learning_summary_rule_sources WHERE summary_id = ?", (summary_id,))
            cursor = connection.execute(
                "DELETE FROM learning_summaries WHERE project_id = ? AND skill = ? AND version = ?",
                (project_id, skill, version),
            )
            return {"projectId": project_id, "skill": skill, "version": version, "deleted": cursor.rowcount == 1}
    finally:
        connection.close()


def _maybe_disable_overlay_from_reviews(
    connection: sqlite3.Connection,
    record: sqlite3.Row,
) -> dict | None:
    metadata = decode_json(record["metadata_json"])
    overlay = metadata.get("appliedOverlay") if isinstance(metadata, dict) else None
    if not isinstance(overlay, dict):
        return None
    overlay_id = overlay.get("id")
    overlay_project = overlay.get("projectId")
    overlay_skill = _normalize_skill(str(overlay.get("skill") or ""))
    overlay_version = overlay.get("version")
    overlay_digest = overlay.get("contentDigest")
    if (not isinstance(overlay_id, str) or overlay_project != record["project_id"]
            or overlay_skill != _normalize_skill(record["skill"])
            or not isinstance(overlay_version, int) or overlay_version < 1
            or not isinstance(overlay_digest, str)):
        return None
    reviewed_count = 0
    negative_count = 0
    rows = connection.execute(
        """SELECT review_status, metadata_json FROM learning_records
           WHERE project_id = ? AND skill = ? AND reviewed = 1""",
        (record["project_id"], overlay_skill),
    ).fetchall()
    for candidate in rows:
        candidate_metadata = decode_json(candidate["metadata_json"])
        candidate_overlay = candidate_metadata.get("appliedOverlay") if isinstance(candidate_metadata, dict) else None
        if not isinstance(candidate_overlay, dict):
            continue
        if (candidate_overlay.get("id") != overlay_id
                or candidate_overlay.get("version") != overlay_version
                or candidate_overlay.get("contentDigest") != overlay_digest):
            continue
        reviewed_count += 1
        if candidate["review_status"] == "EXCLUDED":
            negative_count += 1
    negative_rate = negative_count / reviewed_count if reviewed_count else 0.0
    if reviewed_count <= OVERLAY_ROLLBACK_MIN_REVIEWS or negative_rate <= OVERLAY_ROLLBACK_NEGATIVE_RATE:
        return None
    disabled_at = now()
    cursor = connection.execute(
        """UPDATE skill_overlays SET status = 'DISABLED', disabled_at = ?
           WHERE id = ? AND project_id = ? AND skill = ? AND version = ?
             AND content_digest = ? AND status = 'ACTIVE'""",
        (disabled_at, overlay_id, record["project_id"], overlay_skill, overlay_version, overlay_digest),
    )
    if cursor.rowcount != 1:
        return None
    return {
        "overlayId": overlay_id, "version": overlay_version,
        "reviewedCount": reviewed_count, "negativeCount": negative_count,
        "negativeRate": negative_rate, "disabledAt": disabled_at,
    }


def update_record(payload: dict) -> dict | None:
    project_id = payload.get("projectId")
    record_id = payload.get("recordId")
    action = payload.get("action")
    if not isinstance(project_id, str) or not isinstance(record_id, str) or action not in ALLOWED_ACTIONS:
        return None
    project = next((item for item in projects() if item.get("projectId") == project_id), None)
    if project is None:
        return None
    classic = payload.get("isClassic", False)
    if action != "DELETED" and not isinstance(classic, bool):
        return None
    shared_group_record = None
    for database in _project_databases(project):
        if not database.is_file():
            continue
        connection = connect_database(database, timeout=5)
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                record = connection.execute(
                    "SELECT id, project_id, skill, metadata_json, capture_source, "
                    "shared_capture_id, shared_capture_complete "
                    "FROM learning_records WHERE id = ? AND project_id = ?",
                    (record_id, project_id),
                ).fetchone()
                if record is None:
                    continue
                if record["shared_capture_id"] and not record["shared_capture_complete"]:
                    raise ValueError("shared Hook capture is still finalizing")
                shared_capture_id = _shared_hook_capture_id(dict(record))
                if shared_capture_id is not None:
                    shared_group_record = dict(record)
                    break
                summary_sources_exist = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_summary_sources'"
                ).fetchone()
                if summary_sources_exist and connection.execute(
                    "SELECT 1 FROM learning_summary_sources WHERE record_id = ? LIMIT 1", (record_id,)
                ).fetchone():
                    raise ValueError(
                        "learning record is referenced by a Summary and cannot be modified or deleted"
                    )
                reviewed_at = now()
                if action == "DELETED":
                    cursor = connection.execute(
                        "DELETE FROM learning_records WHERE id = ? AND project_id = ?",
                        (record_id, project_id),
                    )
                else:
                    cursor = connection.execute(
                        """UPDATE learning_records
                           SET review_status = ?, reviewed = 1, edited_content = ?, review_note = ?,
                               reviewed_at = ?, deleted_at = ?, is_classic = ?, classic_reason = ?
                           WHERE id = ? AND project_id = ?""",
                        (action, payload.get("editedContent"), str(payload.get("note") or ""), reviewed_at, None,
                         int(classic), str(payload.get("classicReason") or ""), record_id, project_id),
                    )
                if cursor.rowcount == 1:
                    disabled_overlay = _maybe_disable_overlay_from_reviews(connection, record)
                    return {"updated": True, "disabledOverlay": disabled_overlay}
        finally:
            connection.close()
        if shared_capture_id is not None:
            break
    else:
        return None
    return _update_shared_hook_records(
        project, project_id, shared_capture_id, shared_group_record, payload,
        classic=classic,
    )


def _update_shared_hook_records(
    project: dict, project_id: str, shared_capture_id: str, group_record: dict,
    payload: dict,
    *, classic: bool,
) -> dict:
    def declared_members(record: dict) -> set[str]:
        declared = _hook_capture_metadata(record).get("matchedSkills")
        if not isinstance(declared, list) or not declared:
            raise ValueError("shared Hook review group has no authoritative Skill membership")
        if any(not isinstance(skill, str) or not skill.strip() for skill in declared):
            raise ValueError("shared Hook review group has invalid Skill membership")
        normalized = [skill.strip() for skill in declared]
        if len(set(normalized)) != len(normalized):
            raise ValueError("shared Hook review group has inconsistent Skill membership")
        return set(normalized)

    expected_skills = declared_members(group_record)
    if group_record.get("skill") not in expected_skills:
        raise ValueError("shared Hook review group has inconsistent Skill membership")

    registered = project.get("databases")
    targets: list[tuple[Path, dict]] = []
    members: list[tuple[Path, dict]] = []
    for skill in sorted(expected_skills):
        if isinstance(registered, dict):
            database_value = registered.get(skill)
            if not isinstance(database_value, str) or not database_value.strip():
                raise ValueError(f"shared Hook review database is not registered for Skill: {skill}")
            database = Path(database_value)
        else:
            database = Path(str(project.get("database", "")))
        if not database.is_file():
            raise ValueError(f"shared Hook review database is unavailable for Skill: {skill}")
        connection = connect_database(database, timeout=5)
        try:
            rows = connection.execute(
                "SELECT id, project_id, skill, metadata_json, capture_source, "
                "shared_capture_id, shared_capture_complete "
                "FROM learning_records WHERE project_id = ? AND skill = ? "
                "AND shared_capture_id = ?",
                (project_id, skill, shared_capture_id),
            ).fetchall()
        finally:
            connection.close()
        if len(rows) != 1:
            raise ValueError(f"shared Hook review member is unavailable for Skill: {skill}")
        member = dict(rows[0])
        if declared_members(member) != expected_skills:
            raise ValueError("shared Hook review group has inconsistent Skill membership")
        members.append((database, member))
        if member["capture_source"] == "HOST_HOOK":
            targets.append((database, member))
        elif member["capture_source"] != "SKILL_CONTRACT":
            raise ValueError("shared Hook review group has an invalid capture source")
    if not targets:
        raise ValueError("shared Hook review group has no Hook evidence to review")
    if any(not record["shared_capture_complete"] for _database, record in targets):
        raise ValueError("shared Hook capture is still finalizing")

    reviewed_at = now()
    database_paths = list(dict.fromkeys(database.resolve() for database, _record in members))
    if len(database_paths) > 11:
        raise ValueError("shared Hook review supports at most 11 Skill databases")
    aliases = {database_paths[0]: "main"}
    connection = connect_database(database_paths[0], timeout=5)
    try:
        for index, database in enumerate(database_paths[1:], start=1):
            alias = f"skill_{index}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(database),))
            aliases[database] = alias
        for alias in aliases.values():
            mode = connection.execute(f"PRAGMA {alias}.journal_mode=TRUNCATE").fetchone()[0]
            if str(mode).casefold() != "truncate":
                raise sqlite3.OperationalError(
                    f"shared Hook review requires rollback journaling for {alias}"
                )
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = 0
            updated_skills = []
            for database, record in members:
                alias = aliases[database.resolve()]
                current = connection.execute(
                    "SELECT id, project_id, skill, metadata_json, capture_source, "
                    "shared_capture_id, shared_capture_complete "
                    f"FROM {alias}.learning_records WHERE id = ? AND project_id = ?",
                    (record["id"], project_id),
                ).fetchone()
                current_record = dict(current) if current is not None else None
                if (
                    current_record is None
                    or current_record["skill"] != record["skill"]
                    or current_record["shared_capture_id"] != shared_capture_id
                    or current_record["capture_source"] != record["capture_source"]
                    or declared_members(current_record) != expected_skills
                    or current_record["capture_source"] not in {"HOST_HOOK", "SKILL_CONTRACT"}
                ):
                    raise ValueError("shared Hook review group changed while it was being reviewed")
                if current_record["capture_source"] == "SKILL_CONTRACT":
                    continue
                if not current_record["shared_capture_complete"]:
                    raise ValueError("shared Hook capture is still finalizing")
                if connection.execute(
                    f"SELECT 1 FROM {alias}.learning_summary_sources "
                    "WHERE record_id = ? LIMIT 1",
                    (record["id"],),
                ).fetchone():
                    raise ValueError(
                        "a shared Hook record is referenced by a Summary and cannot be modified or deleted"
                    )
                if payload["action"] == "DELETED":
                    cursor = connection.execute(
                        f"DELETE FROM {alias}.learning_records WHERE id = ? AND project_id = ?",
                        (record["id"], project_id),
                    )
                else:
                    cursor = connection.execute(
                        f"""UPDATE {alias}.learning_records
                           SET review_status = ?, reviewed = 1, edited_content = ?, review_note = ?,
                               reviewed_at = ?, deleted_at = NULL, is_classic = ?, classic_reason = ?
                           WHERE id = ? AND project_id = ?""",
                        (
                            payload["action"], payload.get("editedContent"),
                            str(payload.get("note") or ""), reviewed_at, int(classic),
                            str(payload.get("classicReason") or ""), record["id"], project_id,
                        ),
                    )
                if cursor.rowcount != 1:
                    raise ValueError("shared Hook review member could not be updated")
                updated += 1
                updated_skills.append(current_record["skill"])
    finally:
        connection.close()
    return {
        "updated": True,
        "updatedCount": updated,
        "sharedCaptureId": shared_capture_id,
        "sharedSkills": sorted(updated_skills),
        "disabledOverlay": None,
    }


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
        host_error = _service_host_error(self.headers, self.server.server_port)
        if host_error is not None:
            status, message = host_error
            self.send_json({"error": message}, status)
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Set-Cookie", _service_cookie())
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path in {"/versions", "/versions.html"}:
                body = VERSIONS_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Set-Cookie", _service_cookie())
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path in {"/overlays", "/overlays.html"}:
                body = OVERLAYS_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Set-Cookie", _service_cookie())
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/assets/learning-i18n.js":
                body = I18N_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/projects":
                self.send_json(projects())
            elif parsed.path == "/api/service":
                self.send_json({"pid": os.getpid(), "token": SERVICE_TOKEN})
            elif parsed.path == "/api/records":
                self.send_json(query_records(parse_qs(parsed.query)))
            elif parsed.path == "/api/records-page":
                self.send_json(query_record_page(parse_qs(parsed.query)))
            elif parsed.path == "/api/summaries":
                self.send_json(query_summaries(parse_qs(parsed.query)))
            elif parsed.path == "/api/summary-generation":
                self.send_json(get_summary_generation(parse_qs(parsed.query)))
            elif parsed.path == "/api/summary-generation-estimate":
                self.send_json(get_summary_generation_estimate(parse_qs(parsed.query)))
            elif parsed.path == "/api/summary-evidence":
                self.send_json(summary_evidence(parse_qs(parsed.query)))
            elif parsed.path == "/api/summary-decisions":
                self.send_json(summary_decisions(parse_qs(parsed.query)))
            elif parsed.path == "/api/overlays":
                self.send_json(query_overlays(parse_qs(parsed.query)))
            elif parsed.path == "/api/llm-config":
                self.send_json(llm_config_status())
            elif parsed.path == "/api/hook-status":
                self.send_json(hook_status())
            else:
                self.send_json({"error": "not found"}, 404)
        except SummarySubmissionNotFound as error:
            self.send_json({"error": str(error), "code": "SUMMARY_SUBMISSION_NOT_FOUND"}, 404)
        except SummaryJobNotFound as error:
            self.send_json({"error": str(error), "code": "SUMMARY_JOB_NOT_FOUND"}, 404)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                self.send_json({"error": "database is busy; operation was not committed", "retryable": True}, 503)
            else:
                self.send_json({"error": str(error)}, 500)
        except OSError as error:
            self.send_json({"error": f"local configuration access failed: {error}"}, 500)

    def do_POST(self):
        if self.path not in {"/api/review", "/api/summary-generation", "/api/summary-generation-retry", "/api/create-overlay", "/api/copy-overlay", "/api/review-overlay", "/api/evaluate-publish-overlay", "/api/activate-overlay", "/api/disable-overlay", "/api/delete-overlay", "/api/delete-summary", "/api/review-summary", "/api/llm-config", "/api/project-status", "/api/hook-config"}:
            self.send_json({"error": "not found"}, 404)
            return
        authorization_error = _mutation_request_error(self.headers, self.server.server_port)
        if authorization_error is not None:
            status, message = authorization_error
            self.send_json({"error": message}, status)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/project-status":
                self.send_json(set_project_registration_status(payload))
                return
            if self.path == "/api/hook-config":
                self.send_json(update_global_hook(payload))
                return
            if self.path == "/api/llm-config":
                self.send_json(save_llm_config(payload))
                return
            if self.path == "/api/summary-generation":
                self.send_json(start_summary_generation(payload), 202)
                return
            if self.path == "/api/summary-generation-retry":
                self.send_json(retry_summary_generation(payload), 202)
                return
            if self.path == "/api/create-overlay":
                self.send_json(create_overlay(payload), 201)
                return
            if self.path == "/api/copy-overlay":
                self.send_json(copy_overlay(payload), 201)
                return
            if self.path == "/api/review-overlay":
                self.send_json(review_overlay(payload))
                return
            if self.path == "/api/evaluate-publish-overlay":
                evaluation_result = evaluate_and_publish_overlay(payload)
                self.send_json(evaluation_result, 201 if evaluation_result.get("status") == "PUBLISHED" else 422)
                return
            if self.path == "/api/activate-overlay":
                self.send_json(activate_overlay(payload))
                return
            if self.path == "/api/disable-overlay":
                self.send_json(disable_overlay(payload))
                return
            if self.path == "/api/delete-overlay":
                self.send_json(delete_overlay(payload))
                return
            if self.path == "/api/delete-summary":
                self.send_json(delete_summary(payload))
                return
            if self.path == "/api/review-summary":
                self.send_json(review_summary(payload))
                return
            update_result = update_record(payload)
            if update_result is None:
                self.send_json({"error": "record not found or invalid action"}, 400)
                return
            self.send_json({"ok": True, **update_result})
        except OverlayConflict as error:
            self.send_json({"error": str(error), "code": "OVERLAY_CONFLICT", "overlayId": error.overlay_id,
                            "version": error.version, "replaceable": error.replaceable}, 409)
        except (ValueError, json.JSONDecodeError, sqlite3.IntegrityError) as error:
            self.send_json({"error": str(error)}, 400)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                self.send_json({"error": "database is busy; operation was not committed", "retryable": True}, 503)
            else:
                self.send_json({"error": str(error)}, 500)
        except OSError as error:
            self.send_json({"error": f"local configuration write failed: {error}"}, 500)

    def log_message(self, format, *args):
        return


def serve_review_server(port: int, token: str = "") -> None:
    global SERVICE_TOKEN
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        with _registry_file_lock(SERVICE_OWNER_PATH, timeout=0):
            SERVICE_TOKEN = token or uuid.uuid4().hex
            recover_summary_generation_jobs()
            print(f"Learning review: http://127.0.0.1:{port}")
            server.serve_forever()
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    serve_review_server(args.port, args.token)


if __name__ == "__main__":
    main()
