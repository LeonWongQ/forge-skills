# -*- coding: utf-8 -*-
"""Provider-neutral runtime document contracts and schema validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from .helpers import load_json_file_safe
from .registry_discovery import validate_instance_with_schema


RUNTIME_ENVELOPE_VERSION = "1.1"
STAGE_LEDGER_VERSION = "1.0"
CONTEXT_BUNDLE_VERSION = "1.0"
CLAUDE_CODE_HOST_ADAPTER_ID = "forge.claude_code_host"
CLAUDE_CODE_HOST_ADAPTER_VERSION = "1.0"
CLAUDE_CODE_HOST_REQUEST_VERSION = "1.0"
CLAUDE_CODE_HOST_RESULT_VERSION = "1.0"
CONTEXT_BUNDLE_LAYER_ORDER = (
    "kernel", "runtime", "skills", "packs", "behaviors", "workflow",
    "engine", "domains", "templates", "checklists", "reports",
)


@dataclass(frozen=True)
class ExecutionAdapterRequest:
    """Provider-neutral handoff for one externally executed runtime stage."""

    runtime_id: str
    request_id: str
    request_digest: str
    stage_id: str
    stage_index: int
    attempt: int
    previous_stage_id: Optional[str]
    resolved_context: Dict[str, Any]
    runtime_state: Dict[str, Any]
    template_id: str
    output_schema_path: Optional[str]
    constraints: List[str]
    correlation: Dict[str, Any]
    response_mode: Literal["structured_json"] = "structured_json"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAdapterResult:
    """Normalized external-host result; core code never invokes a provider."""

    runtime_id: str
    request_id: str
    request_digest: str
    status: Literal["succeeded", "failed", "blocked", "skipped"]
    adapter_id: str
    stage_id: str
    stage_index: int
    attempt: int
    adapter_version: Optional[str] = None
    output: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    diagnostics: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def canonical_digest(value: Any) -> str:
    """Return a stable digest for portable JSON-compatible documents."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _schema(root: Path, filename: str) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    path = root / "registry" / "schemas" / filename
    data, error = load_json_file_safe(path)
    if error:
        return None, [{"code": "RUNTIME_SCHEMA_INVALID_JSON", "message": f"Cannot load runtime schema: {path}", "details": {"error": error}}]
    if not isinstance(data, dict):
        return None, [{"code": "RUNTIME_SCHEMA_INVALID", "message": f"Runtime schema must be an object: {path}"}]
    return data, []


def validate_document(root: Path, document: Any, filename: str, document_name: str) -> List[Dict[str, Any]]:
    schema, errors = _schema(root, filename)
    if errors:
        return errors
    assert schema is not None
    return validate_instance_with_schema(document, schema)


def validate_resolved_context(root: Path, manifest: Any) -> List[Dict[str, Any]]:
    return validate_document(root, manifest, "resolved-context.schema.json", "resolved context")


def validate_runtime_state(root: Path, state: Any) -> List[Dict[str, Any]]:
    return validate_document(root, state, "runtime-state.schema.json", "runtime state")


def validate_runtime_envelope(root: Path, envelope: Any) -> List[Dict[str, Any]]:
    errors = validate_document(root, envelope, "runtime-envelope.schema.json", "runtime envelope")
    if errors or not isinstance(envelope, dict):
        return errors
    manifest_stages = [item.get("id") for item in envelope.get("resolved_context", {}).get("context", {}).get("engine", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
    progress = envelope.get("stage_progress", {})
    stages = progress.get("workflow_stages") if isinstance(progress, dict) else None
    index = progress.get("current_stage_index") if isinstance(progress, dict) else None
    active = progress.get("active_request") if isinstance(progress, dict) else None
    if stages != manifest_stages:
        errors.append({"code": "RUNTIME_STAGE_PROGRESS_MISMATCH", "message": "stage progress workflow does not match resolved context"})
        return errors
    if not isinstance(index, int) or index < 0 or index >= len(manifest_stages):
        errors.append({"code": "RUNTIME_STAGE_INDEX_INVALID", "message": "stage progress current index is invalid"})
        return errors
    ledger = envelope.get("ledger", {})
    if ledger.get("runtime_id") != envelope.get("runtime_id"):
        errors.append({"code": "RUNTIME_LEDGER_ID_MISMATCH", "message": "ledger runtime_id does not match envelope"})
    events = ledger.get("events", [])
    if [event.get("sequence") for event in events if isinstance(event, dict)] != list(range(1, len(events) + 1)):
        errors.append({"code": "RUNTIME_LEDGER_SEQUENCE_INVALID", "message": "ledger event sequences are not contiguous"})
    last_advance = next((event for event in reversed(events) if isinstance(event, dict) and event.get("event_type") == "stage_advanced"), None)
    if last_advance:
        expected_stage = last_advance.get("payload", {}).get("to_stage_id")
        if manifest_stages[index] != expected_stage:
            errors.append({"code": "RUNTIME_STAGE_CURSOR_INVALID", "message": "current stage does not follow the latest recorded advance"})
    elif index != 0:
        errors.append({"code": "RUNTIME_STAGE_CURSOR_INVALID", "message": "current stage must begin at the first workflow stage"})
    status = envelope.get("status")
    if status == "awaiting_adapter":
        request = envelope.get("adapter_request") or {}
        if not isinstance(active, dict) or any(request.get(field) != active.get(field) for field in ("request_id", "request_digest", "stage_id", "stage_index", "attempt")):
            errors.append({"code": "RUNTIME_ACTIVE_REQUEST_INVALID", "message": "active request does not match prepared adapter request"})
    elif status in {"ready", "ready_for_validation", "completed", "validation_failed", "failed"} and active is not None:
        errors.append({"code": "RUNTIME_ACTIVE_REQUEST_UNEXPECTED", "message": "runtime status must not retain an active request"})
    elif status == "result_imported":
        result = envelope.get("adapter_result") or {}
        if not isinstance(active, dict) or any(result.get(field) != active.get(field) for field in ("request_id", "request_digest", "stage_id", "stage_index", "attempt")):
            errors.append({"code": "RUNTIME_RESULT_LINK_INVALID", "message": "imported adapter result does not match active request"})
    return errors


def validate_context_bundle(root: Path, bundle: Any) -> List[Dict[str, Any]]:
    return validate_document(root, bundle, "context-bundle.schema.json", "context bundle")


def validate_claude_code_host_request(root: Path, request: Any) -> List[Dict[str, Any]]:
    return validate_document(root, request, "claude-code-host-request.schema.json", "Claude Code host request")


def validate_claude_code_host_result(root: Path, result: Any) -> List[Dict[str, Any]]:
    return validate_document(root, result, "claude-code-host-result.schema.json", "Claude Code host result")


def validate_stage_ledger(root: Path, ledger: Any) -> List[Dict[str, Any]]:
    return validate_document(root, ledger, "stage-ledger.schema.json", "stage ledger")
