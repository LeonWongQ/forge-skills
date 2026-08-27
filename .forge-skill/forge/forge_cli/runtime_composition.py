# -*- coding: utf-8 -*-
"""Runtime envelope initialization and external adapter handoff preparation."""

from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .domain_resolution import resolve_domains
from .output_validation import resolve_template_output_schema
from .query_helpers import find_pack_object_by_id
from .runtime_contracts import ExecutionAdapterRequest, RUNTIME_ENVELOPE_VERSION, canonical_digest, validate_resolved_context, validate_runtime_envelope, validate_runtime_state
from .stage_ledger import append_event, new_ledger


RESULT_STATUSES = {"succeeded", "failed", "blocked", "skipped"}
ADVANCE_ACTIONS = {"next", "retry", "abort"}


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def _selected_pack_domains(root: Path, manifest: Dict[str, Any]) -> list[str]:
    pack_id = manifest.get("selection", {}).get("pack")
    pack = find_pack_object_by_id(root, pack_id) if pack_id else None
    modules = pack.get("modules", {}) if isinstance(pack, dict) else {}
    return list(modules.get("domains", [])) if isinstance(modules, dict) else []


def _workflow_stages(manifest: Dict[str, Any]) -> list[str]:
    return [item["id"] for item in manifest.get("context", {}).get("engine", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _runtime_state(manifest: Dict[str, Any], task_statement: str, user_goal: str, domain_resolution: Dict[str, Any], metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    selection = manifest.get("selection", {})
    metadata = metadata or {}
    return {
        "task_statement": task_statement,
        "user_goal": user_goal,
        "primary_behavior": selection.get("behavior") or "behavior.explain",
        "secondary_behaviors": list(metadata.get("secondary_behaviors", [])),
        "active_domains": domain_resolution["selected_domains"],
        "workflow": selection.get("workflow") or "workflow.full_default",
        "template": selection.get("template") or "template.default",
        "checklists": list(selection.get("checklists", [])),
        "scope": metadata.get("scope", {"in_scope": [task_statement], "out_of_scope": []}),
        "constraints": list(metadata.get("constraints", [])),
        "assumptions": list(metadata.get("assumptions", [])),
        "evidence": list(metadata.get("evidence", [])),
        "findings": list(metadata.get("findings", [])),
        "plan": list(metadata.get("plan", [])),
        "verification_status": metadata.get("verification_status", {"level": "none", "verified": [], "unverified": []}),
        "open_questions": list(metadata.get("open_questions", [])),
        "confidence": metadata.get("confidence", "low"),
    }


def _stage_progress(manifest: Dict[str, Any]) -> Dict[str, Any]:
    stages = _workflow_stages(manifest)
    if not stages:
        raise ValueError("resolved context has no workflow stage")
    return {"workflow_stages": stages, "current_stage_index": 0, "active_request": None, "attempts": {stage: 0 for stage in stages}}


def _current_stage(envelope: Dict[str, Any]) -> tuple[str, int]:
    progress = envelope.get("stage_progress") or {}
    stages = progress.get("workflow_stages") or []
    index = progress.get("current_stage_index")
    if not isinstance(index, int) or index < 0 or index >= len(stages):
        raise ValueError("runtime stage progress has no current workflow stage")
    return stages[index], index


def initialize_runtime(
    root: Path,
    manifest: Dict[str, Any],
    *,
    task_statement: str,
    user_goal: Optional[str] = None,
    artifact_evidence: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
    runtime_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a portable runtime envelope from one successful resolved manifest."""
    errors = validate_resolved_context(root, manifest)
    if errors:
        raise ValueError(f"resolved context validation failed: {errors}")
    if not manifest.get("resolution", {}).get("ok"):
        raise ValueError("cannot initialize runtime from an unresolved context")
    if not task_statement.strip():
        raise ValueError("task_statement must not be empty")

    selection = manifest.get("selection", {})
    eligible = _unique(selection.get("domains", []))
    protected = _unique(_selected_pack_domains(root, manifest))
    sources = selection.get("sources", {})
    if isinstance(sources, dict) and "cli" in sources.get("domains", []):
        protected.extend(eligible)
    domain_result = resolve_domains(root, eligible, task_statement, artifact_evidence, protected)
    state = _runtime_state(manifest, task_statement, user_goal or task_statement, domain_result, metadata)
    state_errors = validate_runtime_state(root, state)
    if state_errors:
        raise ValueError(f"runtime state validation failed: {state_errors}")

    rid = runtime_id or f"runtime.{uuid.uuid4().hex}"
    envelope: Dict[str, Any] = {
        "schema_version": RUNTIME_ENVELOPE_VERSION,
        "runtime_id": rid,
        "status": "initialized",
        "created_at": None,
        "updated_at": None,
        "resolved_context": deepcopy(manifest),
        "resolved_context_digest": canonical_digest(manifest),
        "runtime_state": state,
        "domain_resolution": domain_result,
        "stage_progress": _stage_progress(manifest),
        "ledger": new_ledger(rid),
        "adapter_request": None,
        "adapter_result": None,
        "output_validation": None,
    }
    envelope = append_event(envelope, "runtime_initialized", "runtime", payload={"resolved_context_digest": envelope["resolved_context_digest"]})
    envelope = append_event(envelope, "context_resolved", "runtime", payload={"selection": {key: selection.get(key) for key in ("skill", "pack", "workflow", "template")}})
    envelope = append_event(envelope, "domain_direct_evidence_collected", "runtime", payload={"evidence": domain_result["evidence"], "rejected": domain_result["rejected"]})
    envelope = append_event(envelope, "domain_related_candidates_considered", "runtime", payload={"candidates": domain_result["related_candidates"]})
    envelope = append_event(envelope, "domain_resolution_completed", "runtime", payload={"selected_domains": domain_result["selected_domains"], "confidence": domain_result["confidence"]})
    envelope["status"] = "ready"
    envelope_errors = validate_runtime_envelope(root, envelope)
    if envelope_errors:
        raise ValueError(f"runtime envelope validation failed: {envelope_errors}")
    return envelope


def prepare_adapter_request(root: Path, envelope: Dict[str, Any], stage_id: Optional[str] = None) -> Dict[str, Any]:
    """Prepare the single current provider-neutral adapter request without executing it."""
    errors = validate_runtime_envelope(root, envelope)
    if errors:
        raise ValueError(f"runtime envelope validation failed: {errors}")
    if envelope.get("status") != "ready":
        raise ValueError("runtime must be ready before preparing an adapter request")
    updated = deepcopy(envelope)
    current_stage, stage_index = _current_stage(updated)
    if stage_id and stage_id != current_stage:
        raise ValueError(f"requested stage is not the current workflow stage: {stage_id}")
    if updated["stage_progress"].get("active_request") is not None:
        raise ValueError("runtime already has an active adapter request")
    state = updated["runtime_state"]
    schema_path, schema_errors = resolve_template_output_schema(root, state["template"])
    if schema_errors:
        raise ValueError(f"cannot resolve output schema: {schema_errors}")
    attempt = updated["stage_progress"]["attempts"][current_stage] + 1
    request_id = f"adapter_request.{uuid.uuid4().hex}"
    request = ExecutionAdapterRequest(
        runtime_id=updated["runtime_id"], request_id=request_id, request_digest="pending", stage_id=current_stage,
        stage_index=stage_index, attempt=attempt,
        previous_stage_id=updated["stage_progress"]["workflow_stages"][stage_index - 1] if stage_index else None,
        resolved_context=updated["resolved_context"], runtime_state=state, template_id=state["template"],
        output_schema_path=str(schema_path.relative_to(root.resolve())).replace("\\", "/") if schema_path else None,
        constraints=state["constraints"],
        correlation={"resolved_context_digest": updated["resolved_context_digest"], "ledger_sequence": len(updated["ledger"]["events"]) + 1},
    ).to_dict()
    request["request_digest"] = canonical_digest({key: value for key, value in request.items() if key != "request_digest"})
    updated["stage_progress"]["attempts"][current_stage] = attempt
    updated["stage_progress"]["active_request"] = {key: request[key] for key in ("request_id", "request_digest", "stage_id", "stage_index", "attempt")}
    updated["adapter_request"] = request
    updated["adapter_result"] = None
    updated = append_event(updated, "adapter_request_prepared", "runtime", stage_id=current_stage, payload={"template_id": state["template"], "response_mode": "structured_json", **updated["stage_progress"]["active_request"]})
    updated["status"] = "awaiting_adapter"
    return updated


def import_adapter_result(root: Path, envelope: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Import one normalized result that exactly matches the active adapter request."""
    errors = validate_runtime_envelope(root, envelope)
    if errors:
        raise ValueError(f"runtime envelope validation failed: {errors}")
    if envelope.get("status") != "awaiting_adapter":
        raise ValueError("runtime must be awaiting an adapter result")
    active = envelope.get("stage_progress", {}).get("active_request")
    if not isinstance(active, dict):
        raise ValueError("runtime has no active adapter request")
    if result.get("runtime_id") != envelope.get("runtime_id"):
        raise ValueError("adapter result runtime_id does not match envelope")
    if result.get("status") not in RESULT_STATUSES:
        raise ValueError("adapter result has invalid status")
    for field in ("request_id", "request_digest", "stage_id", "stage_index", "attempt"):
        if result.get(field) != active.get(field):
            raise ValueError(f"adapter result {field} does not match active request")
    updated = deepcopy(envelope)
    updated["adapter_result"] = deepcopy(result)
    updated = append_event(updated, "adapter_result_received", "adapter", stage_id=active["stage_id"], payload={"status": result["status"], "adapter_id": result.get("adapter_id"), **active}, diagnostics=result.get("diagnostics"), provider_metadata=result.get("metadata"))
    stages = updated.get("stage_progress", {}).get("workflow_stages", [])
    is_final_stage = bool(stages) and active.get("stage_index") == len(stages) - 1
    if is_final_stage and result.get("status") == "succeeded":
        # Each selected Skill contributes at most one independent final result.
        try:
            from .learning_collector import collect_imported_result
            collect_imported_result(root, updated, result, project=Path.cwd())
        except Exception:
            pass
    updated["status"] = "result_imported"
    return updated


def advance_runtime(root: Path, envelope: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Explicitly advance, retry, or abort after a linked imported result."""
    errors = validate_runtime_envelope(root, envelope)
    if errors:
        raise ValueError(f"runtime envelope validation failed: {errors}")
    if action not in ADVANCE_ACTIONS:
        raise ValueError(f"unsupported runtime advance action: {action}")
    if envelope.get("status") != "result_imported":
        raise ValueError("runtime must have an imported result before advancing")
    result = envelope.get("adapter_result") or {}
    active = envelope.get("stage_progress", {}).get("active_request")
    if not isinstance(active, dict):
        raise ValueError("runtime has no active request to advance")
    status = result.get("status")
    updated = deepcopy(envelope)
    stage_id, stage_index = _current_stage(updated)
    if action == "next":
        if status != "succeeded":
            raise ValueError("only a succeeded adapter result may advance the workflow")
        updated["stage_progress"]["active_request"] = None
        if stage_index + 1 == len(updated["stage_progress"]["workflow_stages"]):
            updated = append_event(updated, "workflow_stages_completed", "runtime", stage_id=stage_id, payload={"request_id": active["request_id"], "stage_index": stage_index})
            updated["status"] = "ready_for_validation"
        else:
            next_stage = updated["stage_progress"]["workflow_stages"][stage_index + 1]
            updated = append_event(updated, "stage_advanced", "runtime", stage_id=stage_id, payload={"request_id": active["request_id"], "from_stage_index": stage_index, "to_stage_id": next_stage})
            updated["stage_progress"]["current_stage_index"] = stage_index + 1
            updated["status"] = "ready"
    elif action == "retry":
        if status not in {"failed", "blocked"}:
            raise ValueError("only failed or blocked adapter results may be retried")
        updated["stage_progress"]["active_request"] = None
        updated = append_event(updated, "stage_retry_requested", "runtime", stage_id=stage_id, payload={"request_id": active["request_id"], "status": status, "attempt": active["attempt"]})
        updated["status"] = "ready"
    else:
        if status not in {"failed", "blocked"}:
            raise ValueError("only failed or blocked adapter results may abort a runtime")
        updated["stage_progress"]["active_request"] = None
        updated = append_event(updated, "runtime_failed", "runtime", stage_id=stage_id, payload={"request_id": active["request_id"], "status": status})
        updated["status"] = "failed"
    return updated
