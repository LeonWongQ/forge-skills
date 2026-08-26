# -*- coding: utf-8 -*-
"""Read-only discovery of caller-owned resumable Runtime Envelopes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .helpers import load_json_file_safe
from .runtime_contracts import validate_runtime_envelope


RESUMABLE_STATUSES = {"ready", "awaiting_adapter", "result_imported", "ready_for_validation"}


def _current_stage(envelope: Dict[str, Any]) -> tuple[str | None, int | None]:
    progress = envelope.get("stage_progress")
    if not isinstance(progress, dict):
        return None, None
    stages = progress.get("workflow_stages")
    index = progress.get("current_stage_index")
    if not isinstance(stages, list) or not isinstance(index, int) or not 0 <= index < len(stages):
        return None, None
    stage_id = stages[index]
    return stage_id if isinstance(stage_id, str) else None, index


def discover_resumable_runtimes(root: Path, directory: Path) -> Dict[str, Any]:
    """List valid nonterminal envelopes directly inside one explicit directory."""
    resolved_directory = directory.resolve()
    result: Dict[str, Any] = {
        "command": "runtime-list-paused",
        "directory": str(resolved_directory),
        "candidates": [],
        "diagnostics": [],
        "summary": {"scanned": 0, "resumable": 0, "terminal": 0, "invalid": 0},
    }
    if not resolved_directory.exists():
        return result
    if not resolved_directory.is_dir():
        result["diagnostics"].append({
            "code": "RUNTIME_DIRECTORY_INVALID",
            "message": "runtime discovery path is not a directory",
            "path": str(resolved_directory),
        })
        return result

    for path in sorted(resolved_directory.glob("*.json"), key=lambda item: item.name.lower()):
        result["summary"]["scanned"] += 1
        document, error = load_json_file_safe(path)
        relative_path = path.name
        if error or not isinstance(document, dict):
            result["summary"]["invalid"] += 1
            result["diagnostics"].append({
                "code": "RUNTIME_DOCUMENT_INVALID_JSON",
                "message": "runtime candidate is not valid JSON object",
                "path": relative_path,
            })
            continue
        errors = validate_runtime_envelope(root, document)
        if errors:
            result["summary"]["invalid"] += 1
            result["diagnostics"].append({
                "code": "RUNTIME_DOCUMENT_INVALID",
                "message": "runtime candidate failed envelope validation",
                "path": relative_path,
                "errors": errors,
            })
            continue
        status = document["status"]
        if status not in RESUMABLE_STATUSES:
            result["summary"]["terminal"] += 1
            continue
        stage_id, stage_index = _current_stage(document)
        active_request = document.get("stage_progress", {}).get("active_request") or {}
        task_statement = document.get("runtime_state", {}).get("task_statement")
        result["summary"]["resumable"] += 1
        result["candidates"].append({
            "path": relative_path,
            "runtime_id": document["runtime_id"],
            "task_statement": task_statement,
            "status": status,
            "current_stage_id": stage_id,
            "current_stage_index": stage_index,
            "attempt": active_request.get("attempt", 0),
            "resumable": True,
        })
    return result
