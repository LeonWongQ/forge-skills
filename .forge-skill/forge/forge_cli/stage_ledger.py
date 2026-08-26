# -*- coding: utf-8 -*-
"""Append-only runtime ledger helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from .runtime_contracts import STAGE_LEDGER_VERSION


TERMINAL_EVENT_TYPES = {"runtime_failed", "output_validation_completed"}
RESULT_EVENTS = {"adapter_result_received", "manual_output_received"}


def new_ledger(runtime_id: str) -> Dict[str, Any]:
    return {"ledger_version": STAGE_LEDGER_VERSION, "runtime_id": runtime_id, "events": []}


def workflow_stages(envelope: Dict[str, Any]) -> set[str]:
    return {
        item.get("id")
        for item in envelope.get("resolved_context", {}).get("context", {}).get("engine", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def append_event(
    envelope: Dict[str, Any],
    event_type: str,
    actor: str,
    *,
    stage_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    updated = deepcopy(envelope)
    ledger = updated["ledger"]
    events = ledger["events"]
    if events and events[-1].get("event_type") in TERMINAL_EVENT_TYPES:
        raise ValueError("cannot append an event after a terminal ledger event")
    if stage_id and stage_id not in workflow_stages(updated):
        raise ValueError(f"stage is not part of resolved workflow: {stage_id}")
    if event_type == "output_validation_completed" and updated.get("status") != "ready_for_validation":
        raise ValueError("output validation requires every workflow stage to be completed")
    event = {
        "sequence": len(events) + 1,
        "event_type": event_type,
        "actor": actor,
        "stage_id": stage_id,
        "timestamp": None,
        "payload": payload or {},
    }
    if diagnostics:
        event["diagnostics"] = diagnostics
    if provider_metadata:
        event["provider_metadata"] = provider_metadata
    events.append(event)
    return updated
