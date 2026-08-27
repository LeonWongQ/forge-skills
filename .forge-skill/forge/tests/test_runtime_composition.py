# -*- coding: utf-8 -*-
"""Tests for the thin provider-neutral runtime foundation."""

from copy import deepcopy
from pathlib import Path

import pytest

from forge_cli.cli import _execute_route
from forge_cli.runtime_composition import advance_runtime, import_adapter_result, initialize_runtime, prepare_adapter_request
from forge_cli.runtime_output_validation import validate_runtime_output
from forge_cli.resolved_context import build_context_from_route
from forge_cli.stage_ledger import append_event


ROOT = Path(__file__).resolve().parents[1]


def _runtime():
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "帮我 review 一个 spring service 改动"))
    return initialize_runtime(ROOT, manifest, task_statement="帮我 review 一个 spring service 改动", runtime_id="runtime.test")


def _result(prepared, status="succeeded", output=None):
    request = prepared["adapter_request"]
    return {
        "runtime_id": prepared["runtime_id"],
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "stage_id": request["stage_id"],
        "stage_index": request["stage_index"],
        "attempt": request["attempt"],
        "status": status,
        "adapter_id": "fixture",
        "output": {} if output is None else output,
        "evidence": [],
        "diagnostics": [],
        "metadata": {},
    }


def _advance_to_final(runtime):
    while runtime["status"] != "ready_for_validation":
        prepared = prepare_adapter_request(ROOT, runtime)
        imported = import_adapter_result(ROOT, prepared, _result(prepared))
        runtime = advance_runtime(ROOT, imported, "next")
    return runtime


def test_runtime_initialization_embeds_manifest_and_refines_domains():
    envelope = _runtime()

    assert envelope["status"] == "ready"
    assert envelope["resolved_context"]["resolution"]["ok"] is True
    assert envelope["runtime_state"]["active_domains"] == ["domain.java", "domain.spring", "domain.testing"]
    assert envelope["stage_progress"]["current_stage_index"] == 0
    assert envelope["stage_progress"]["active_request"] is None
    assert [event["event_type"] for event in envelope["ledger"]["events"]] == [
        "runtime_initialized", "context_resolved", "domain_direct_evidence_collected",
        "domain_related_candidates_considered", "domain_resolution_completed",
    ]


def test_prepare_import_and_advance_are_provider_neutral():
    prepared = prepare_adapter_request(ROOT, _runtime())

    assert prepared["status"] == "awaiting_adapter"
    assert prepared["adapter_request"]["response_mode"] == "structured_json"
    assert prepared["adapter_request"]["stage_id"] == "engine.discover"
    with pytest.raises(ValueError, match="must be ready"):
        prepare_adapter_request(ROOT, prepared)

    imported = import_adapter_result(ROOT, prepared, _result(prepared))
    assert imported["status"] == "result_imported"
    assert imported["ledger"]["events"][-1]["event_type"] == "adapter_result_received"

    advanced = advance_runtime(ROOT, imported, "next")
    assert advanced["status"] == "ready"
    assert advanced["stage_progress"]["current_stage_index"] == 1
    assert advanced["stage_progress"]["active_request"] is None


def test_runtime_rejects_unknown_stage_and_unlinked_result():
    with pytest.raises(ValueError, match="stage is not part"):
        append_event(_runtime(), "adapter_request_prepared", "runtime", stage_id="engine.unknown")
    prepared = prepare_adapter_request(ROOT, _runtime())
    wrong = _result(prepared)
    wrong["request_id"] = "adapter_request.stale"
    with pytest.raises(ValueError, match="request_id"):
        import_adapter_result(ROOT, prepared, wrong)


def test_retry_and_abort_preserve_current_stage_and_attempts():
    prepared = prepare_adapter_request(ROOT, _runtime())
    imported = import_adapter_result(ROOT, prepared, _result(prepared, "blocked"))
    retried = advance_runtime(ROOT, imported, "retry")
    assert retried["status"] == "ready"
    assert retried["stage_progress"]["current_stage_index"] == 0

    prepared_again = prepare_adapter_request(ROOT, retried)
    assert prepared_again["adapter_request"]["attempt"] == 2
    imported_again = import_adapter_result(ROOT, prepared_again, _result(prepared_again, "failed"))
    aborted = advance_runtime(ROOT, imported_again, "abort")
    assert aborted["status"] == "failed"
    with pytest.raises(ValueError, match="must be ready"):
        prepare_adapter_request(ROOT, aborted)


def test_runtime_output_validation_requires_final_linked_result():
    ready = _advance_to_final(_runtime())
    output = {"overall_assessment": "ok", "findings": []}
    final = deepcopy(ready)
    final["adapter_result"]["output"] = output
    result = validate_runtime_output(ROOT, final, output)

    assert result["valid"]
    assert result["template_id"] == "template.review_report"
    assert result["envelope"]["ledger"]["events"][-1]["event_type"] == "output_validation_completed"

    premature = validate_runtime_output(ROOT, _runtime(), output)
    assert not premature["valid"]
    assert any(error["code"] == "RUNTIME_NOT_READY_FOR_VALIDATION" for error in premature["errors"])


def test_learning_collection_runs_once_for_final_skill_result(monkeypatch):
    calls = []

    def collect(root, envelope, result, *, project):
        calls.append((envelope["runtime_id"], result["stage_id"], project))

    monkeypatch.setattr("forge_cli.learning_collector.collect_imported_result", collect)

    ready = _advance_to_final(_runtime())

    assert ready["status"] == "ready_for_validation"
    assert calls == [("runtime.test", "engine.delivery", Path.cwd())]
