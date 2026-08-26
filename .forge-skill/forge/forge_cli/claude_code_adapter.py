# -*- coding: utf-8 -*-
"""Build and validate SDK-free Claude Code host handoff artifacts."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .runtime_contracts import (
    CLAUDE_CODE_HOST_ADAPTER_ID,
    CLAUDE_CODE_HOST_ADAPTER_VERSION,
    CLAUDE_CODE_HOST_REQUEST_VERSION,
    CLAUDE_CODE_HOST_RESULT_VERSION,
    CONTEXT_BUNDLE_LAYER_ORDER,
    canonical_digest,
    validate_claude_code_host_request,
    validate_claude_code_host_result,
    validate_context_bundle,
    validate_resolved_context,
    validate_runtime_envelope,
)


RESULT_SCHEMA_PATH = "registry/schemas/claude-code-host-result.schema.json"
_SEGMENT_KINDS = (
    "host_boundary",
    "stable_instruction",
    "runtime_state",
    "stage_contract",
    "host_result_request",
)


def _error(code: str, message: str, **details: Any) -> ValueError:
    suffix = f" ({details})" if details else ""
    return ValueError(f"{code}: {message}{suffix}")


def _content_digest(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _require_no_errors(code: str, message: str, errors: list[dict[str, Any]]) -> None:
    if errors:
        raise _error(code, message, errors=errors)


def _validate_bundle_integrity(root: Path, bundle: Dict[str, Any]) -> None:
    _require_no_errors(
        "CLAUDE_CODE_BUNDLE_INVALID",
        "Context Bundle schema validation failed",
        validate_context_bundle(root, bundle),
    )
    projection = deepcopy(bundle)
    projection.pop("bundle_digest", None)
    if canonical_digest(projection) != bundle.get("bundle_digest"):
        raise _error("CLAUDE_CODE_BUNDLE_DIGEST_MISMATCH", "Context Bundle digest does not match content")

    expected_layers = [layer for layer in CONTEXT_BUNDLE_LAYER_ORDER if layer not in {"workflow", "packs"}]
    previous = -1
    seen: set[tuple[str, str]] = set()
    for layer in bundle["layers"]:
        layer_id = layer["id"]
        try:
            index = expected_layers.index(layer_id)
        except ValueError as error:
            raise _error("CLAUDE_CODE_BUNDLE_LAYER_INVALID", "Context Bundle contains an unsupported materialized layer", layer=layer_id) from error
        if index <= previous:
            raise _error("CLAUDE_CODE_BUNDLE_LAYER_ORDER", "Context Bundle layers are not in canonical order", layer=layer_id)
        previous = index
        for position, module in enumerate(layer["modules"]):
            if module["layer"] != layer_id:
                raise _error("CLAUDE_CODE_BUNDLE_MODULE_LAYER", "module layer does not match containing layer", module_id=module["id"])
            if module["position"] != position:
                raise _error("CLAUDE_CODE_BUNDLE_POSITION", "module position does not match containing order", module_id=module["id"])
            key = (layer_id, module["id"])
            if key in seen:
                raise _error("CLAUDE_CODE_BUNDLE_DUPLICATE_MODULE", "Context Bundle contains duplicate module", layer=layer_id, module_id=module["id"])
            seen.add(key)
            content = module["content"]
            if "\x00" in content:
                raise _error("CLAUDE_CODE_BUNDLE_NUL_CONTENT", "Context Bundle module contains NUL content", module_id=module["id"])
            if len(content.encode("utf-8")) != module["byte_size"]:
                raise _error("CLAUDE_CODE_BUNDLE_BYTE_SIZE", "Context Bundle module byte size does not match content", module_id=module["id"])
            if _content_digest(content) != module["content_digest"]:
                raise _error("CLAUDE_CODE_BUNDLE_CONTENT_DIGEST", "Context Bundle module content digest does not match content", module_id=module["id"])


def _validate_envelope_integrity(root: Path, envelope: Dict[str, Any]) -> None:
    _require_no_errors(
        "CLAUDE_CODE_ENVELOPE_INVALID",
        "Runtime Envelope schema validation failed",
        validate_runtime_envelope(root, envelope),
    )
    manifest = envelope["resolved_context"]
    _require_no_errors(
        "CLAUDE_CODE_MANIFEST_INVALID",
        "embedded resolved context schema validation failed",
        validate_resolved_context(root, manifest),
    )
    if canonical_digest(manifest) != envelope.get("resolved_context_digest"):
        raise _error("CLAUDE_CODE_MANIFEST_DIGEST_MISMATCH", "Runtime Envelope resolved-context digest does not match embedded manifest")


def _available_stages(envelope: Dict[str, Any]) -> list[str]:
    return [entry.get("id") for entry in envelope["resolved_context"]["context"].get("engine", []) if isinstance(entry, dict) and isinstance(entry.get("id"), str)]


def _resolve_stage(envelope: Dict[str, Any], stage_id: Optional[str]) -> str:
    request = envelope.get("adapter_request") or {}
    progress = envelope.get("stage_progress") or {}
    stages = progress.get("workflow_stages") or _available_stages(envelope)
    current_index = progress.get("current_stage_index", 0)
    current_stage = stages[current_index] if isinstance(current_index, int) and 0 <= current_index < len(stages) else None
    selected = stage_id or request.get("stage_id") or current_stage
    if not selected or selected not in stages:
        raise _error("CLAUDE_CODE_STAGE_INVALID", "selected stage is not part of the resolved workflow", stage_id=selected)
    if current_stage and selected != current_stage:
        raise _error("CLAUDE_CODE_STAGE_NOT_CURRENT", "selected stage is not the current workflow stage", stage_id=selected)
    return selected


def _validate_generic_request(envelope: Dict[str, Any], stage_id: str) -> Dict[str, Any]:
    request = envelope.get("adapter_request") or {}
    if not request:
        return {}
    state = envelope["runtime_state"]
    if request.get("runtime_id") != envelope["runtime_id"]:
        raise _error("CLAUDE_CODE_GENERIC_REQUEST_RUNTIME_MISMATCH", "generic adapter request runtime_id does not match envelope")
    if request.get("stage_id") != stage_id:
        raise _error("CLAUDE_CODE_GENERIC_REQUEST_STAGE_MISMATCH", "generic adapter request stage does not match selected stage")
    if request.get("correlation", {}).get("resolved_context_digest") != envelope["resolved_context_digest"]:
        raise _error("CLAUDE_CODE_GENERIC_REQUEST_DIGEST_MISMATCH", "generic adapter request resolved-context digest does not match envelope")
    if request.get("template_id") != state["template"]:
        raise _error("CLAUDE_CODE_GENERIC_REQUEST_TEMPLATE_MISMATCH", "generic adapter request template does not match runtime state")
    if request.get("runtime_state") != state:
        raise _error("CLAUDE_CODE_GENERIC_REQUEST_STATE_MISMATCH", "generic adapter request runtime state does not match envelope")
    return request


def _segment(position: int, kind: str, title: str, content: str) -> Dict[str, Any]:
    return {"position": position, "kind": kind, "title": title, "content": content, "content_digest": _content_digest(content)}


def _stable_instruction_content(bundle: Dict[str, Any]) -> str:
    blocks = []
    for layer in bundle["layers"]:
        for module in layer["modules"]:
            blocks.append(
                "\n".join((
                    f"<!-- forge-module id={module['id']} layer={module['layer']} path={module['path']} digest={module['content_digest']} -->",
                    module["content"],
                ))
            )
    return "\n\n".join(blocks)


def _build_segments(envelope: Dict[str, Any], bundle: Dict[str, Any], stage_id: str, generic_request: Dict[str, Any]) -> list[Dict[str, Any]]:
    state = envelope["runtime_state"]
    workflow = bundle["workflow"]
    host_boundary = (
        "# Forge Claude Code Host Boundary\n\n"
        "This artifact is caller-managed preparation only. Forge does not invoke Claude Code, "
        "grant tool permissions, select a workspace, execute tools, decide retries, "
        "request approvals, stream output, or advance workflow stages. "
        "Apply host permissions and user approvals independently."
    )
    runtime_state = {
        key: state[key]
        for key in (
            "task_statement", "user_goal", "scope", "constraints", "assumptions", "evidence",
            "findings", "plan", "verification_status", "open_questions", "confidence",
        )
    }
    stage_contract = {
        "stage_id": stage_id,
        "stage_index": generic_request.get("stage_index"),
        "attempt": generic_request.get("attempt"),
        "workflow": workflow,
        "template_id": state["template"],
        "output_schema_path": generic_request.get("output_schema_path"),
        "response_mode": generic_request.get("response_mode", "structured_json"),
        "correlation": generic_request.get("correlation", {"resolved_context_digest": envelope["resolved_context_digest"]}),
    }
    host_result = (
        "# Required Host Result\n\n"
        "Return a JSON document conforming to the provided result skeleton. Preserve all linkage fields "
        "exactly. The host owns result content, evidence, diagnostics, and metadata."
    )
    contents = (
        ("host_boundary", "Host Boundary", host_boundary),
        ("stable_instruction", "Stable Forge Instructions", _stable_instruction_content(bundle)),
        ("runtime_state", "Dynamic Runtime State", "# Dynamic Runtime State\n\n```json\n" + _canonical_json(runtime_state) + "\n```"),
        ("stage_contract", "Selected Stage and Output Contract", "# Selected Stage and Output Contract\n\n```json\n" + _canonical_json(stage_contract) + "\n```"),
        ("host_result_request", "Host Result Request", host_result),
    )
    return [_segment(position, kind, title, content) for position, (kind, title, content) in enumerate(contents)]


def _render_task_prompt(segments: Iterable[Dict[str, Any]]) -> str:
    return "\n\n".join(segment["content"] for segment in segments)


def build_claude_code_host_request(
    root: Path,
    envelope: Dict[str, Any],
    bundle: Dict[str, Any],
    *,
    stage_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an auditable, caller-managed Claude Code host request without execution."""
    _validate_envelope_integrity(root, envelope)
    _validate_bundle_integrity(root, bundle)
    if bundle["runtime_id"] != envelope["runtime_id"]:
        raise _error("CLAUDE_CODE_RUNTIME_MISMATCH", "Context Bundle runtime_id does not match Runtime Envelope")
    if bundle["source"]["resolved_context_digest"] != envelope["resolved_context_digest"]:
        raise _error("CLAUDE_CODE_CONTEXT_LINK_MISMATCH", "Context Bundle resolved-context digest does not match Runtime Envelope")

    selected_stage = _resolve_stage(envelope, stage_id)
    generic_request = _validate_generic_request(envelope, selected_stage)
    segments = _build_segments(envelope, bundle, selected_stage, generic_request)
    task_prompt = _render_task_prompt(segments)
    rid = request_id or f"claude_code_request.{uuid.uuid4().hex}"
    runtime_envelope_digest = canonical_digest(envelope)
    result_skeleton = {
        "schema_version": CLAUDE_CODE_HOST_RESULT_VERSION,
        "runtime_id": envelope["runtime_id"],
        "request_id": rid,
        "request_digest": "pending",
        "adapter_id": CLAUDE_CODE_HOST_ADAPTER_ID,
        "adapter_version": CLAUDE_CODE_HOST_ADAPTER_VERSION,
        "stage_id": selected_stage,
        "stage_index": generic_request["stage_index"],
        "attempt": generic_request["attempt"],
        "generic_linkage": {
            "request_id": generic_request["request_id"],
            "request_digest": generic_request["request_digest"],
        },
        "status": "succeeded",
        "linkage": {
            "resolved_context_digest": envelope["resolved_context_digest"],
            "context_bundle_digest": bundle["bundle_digest"],
        },
        "output": {},
        "evidence": [],
        "diagnostics": [],
        "metadata": {},
    }
    request = {
        "schema_version": CLAUDE_CODE_HOST_REQUEST_VERSION,
        "request_id": rid,
        "adapter": {
            "id": CLAUDE_CODE_HOST_ADAPTER_ID,
            "version": CLAUDE_CODE_HOST_ADAPTER_VERSION,
            "execution": "caller_managed",
            "sdk_free": True,
        },
        "runtime": {
            "runtime_id": envelope["runtime_id"],
            "runtime_envelope_digest": runtime_envelope_digest,
            "resolved_context_digest": envelope["resolved_context_digest"],
            "stage_id": selected_stage,
        "stage_index": generic_request.get("stage_index"),
        "attempt": generic_request.get("attempt"),
        },
        "context_bundle": {
            "bundle_id": bundle["bundle_id"],
            "bundle_digest": bundle["bundle_digest"],
            "resolved_context_digest": bundle["source"]["resolved_context_digest"],
        },
        "prompt": {
            "format": "markdown",
            "segments": segments,
            "task_prompt": task_prompt,
            "task_prompt_digest": _content_digest(task_prompt),
        },
        "result_contract": {
            "schema_version": CLAUDE_CODE_HOST_RESULT_VERSION,
            "required_result_schema": RESULT_SCHEMA_PATH,
            "result_skeleton": result_skeleton,
        },
    }
    request["request_digest"] = canonical_digest(request)
    request["result_contract"]["result_skeleton"]["request_digest"] = request["request_digest"]
    _require_no_errors(
        "CLAUDE_CODE_REQUEST_SCHEMA_INVALID",
        "generated Claude Code host request failed schema validation",
        validate_claude_code_host_request(root, request),
    )
    return request


def validate_and_normalize_claude_code_host_result(root: Path, request: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a host result and return a generic adapter-result-compatible document."""
    _require_no_errors(
        "CLAUDE_CODE_REQUEST_INVALID",
        "Claude Code host request schema validation failed",
        validate_claude_code_host_request(root, request),
    )
    request_projection = deepcopy(request)
    request_digest = request_projection.pop("request_digest", None)
    request_projection["result_contract"]["result_skeleton"]["request_digest"] = "pending"
    if canonical_digest(request_projection) != request_digest:
        raise _error("CLAUDE_CODE_REQUEST_DIGEST_MISMATCH", "Claude Code host request digest does not match request content")
    _require_no_errors(
        "CLAUDE_CODE_RESULT_INVALID",
        "Claude Code host result schema validation failed",
        validate_claude_code_host_result(root, result),
    )
    expected = request["result_contract"]["result_skeleton"]
    for key in ("runtime_id", "request_id", "request_digest", "adapter_id", "adapter_version", "stage_id", "stage_index", "attempt", "generic_linkage"):
        if result.get(key) != expected.get(key):
            raise _error("CLAUDE_CODE_RESULT_LINK_MISMATCH", "Claude Code host result does not match prepared request", field=key)
    for key in ("resolved_context_digest", "context_bundle_digest"):
        if result.get("linkage", {}).get(key) != expected["linkage"][key]:
            raise _error("CLAUDE_CODE_RESULT_LINK_MISMATCH", "Claude Code host result linkage does not match prepared request", field=key)
    return {
        "runtime_id": result["runtime_id"],
        "request_id": result["generic_linkage"]["request_id"],
        "request_digest": result["generic_linkage"]["request_digest"],
        "status": result["status"],
        "adapter_id": result["adapter_id"],
        "adapter_version": result["adapter_version"],
        "stage_id": result["stage_id"],
        "stage_index": result["stage_index"],
        "attempt": result["attempt"],
        "output": deepcopy(result["output"]),
        "evidence": deepcopy(result["evidence"]),
        "diagnostics": deepcopy(result["diagnostics"]),
        "metadata": deepcopy(result["metadata"]),
    }
