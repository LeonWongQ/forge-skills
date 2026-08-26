# -*- coding: utf-8 -*-
"""State-linked structured output validation for runtime envelopes."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from .output_validation import validate_template_document
from .runtime_contracts import validate_runtime_envelope, validate_runtime_state
from .stage_ledger import append_event


def validate_runtime_output(root: Path, envelope: Dict[str, Any], document: Any) -> Dict[str, Any]:
    """Validate a document against the runtime-selected template and state links."""
    errors = []
    errors.extend(validate_runtime_envelope(root, envelope))
    state = envelope.get("runtime_state") if isinstance(envelope, dict) else None
    if state is not None:
        errors.extend(validate_runtime_state(root, state))
    if errors:
        return {"command": "validate-runtime-output", "valid": False, "template_id": None, "errors": errors, "envelope": envelope}

    result = validate_template_document(root, state["template"], document)
    result["command"] = "validate-runtime-output"
    result["runtime_id"] = envelope["runtime_id"]
    linkage_errors = []
    adapter = envelope.get("adapter_result")
    if envelope.get("status") != "ready_for_validation":
        linkage_errors.append({"code": "RUNTIME_NOT_READY_FOR_VALIDATION", "message": "Runtime output validation requires all workflow stages to be explicitly completed"})
    elif not adapter:
        linkage_errors.append({"code": "RUNTIME_RESULT_MISSING", "message": "Runtime output validation requires the final imported adapter result"})
    elif adapter.get("runtime_id") != envelope["runtime_id"]:
        linkage_errors.append({"code": "RUNTIME_RESULT_ID_MISMATCH", "message": "Imported adapter result does not belong to this runtime"})
    elif document != adapter.get("output"):
        linkage_errors.append({"code": "RUNTIME_OUTPUT_LINK_MISMATCH", "message": "Validation input does not match the final linked adapter output"})
    result["errors"] = result["errors"] + linkage_errors
    result["valid"] = not result["errors"]

    updated = deepcopy(envelope)
    try:
        updated = append_event(updated, "output_validation_completed", "validator", payload={"valid": result["valid"], "template_id": state["template"]})
        updated["output_validation"] = {key: value for key, value in result.items() if key != "envelope"}
        updated["status"] = "completed" if result["valid"] else "validation_failed"
    except ValueError as error:
        result["errors"].append({"code": "RUNTIME_LEDGER_INVALID", "message": str(error)})
        result["valid"] = False
    result["envelope"] = updated
    return result
