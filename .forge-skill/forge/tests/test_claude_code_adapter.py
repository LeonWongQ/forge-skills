# -*- coding: utf-8 -*-
"""Tests for SDK-free Claude Code host request and result artifacts."""

from copy import deepcopy
from pathlib import Path

import pytest

from forge_cli.claude_code_adapter import build_claude_code_host_request, validate_and_normalize_claude_code_host_result
from forge_cli.cli import _execute_route
from forge_cli.context_bundle import build_context_bundle
from forge_cli.runtime_composition import import_adapter_result, initialize_runtime, prepare_adapter_request
from forge_cli.runtime_contracts import canonical_digest, validate_claude_code_host_request
from forge_cli.resolved_context import build_context_from_route


ROOT = Path(__file__).resolve().parents[1]


def _prepared_runtime():
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "帮我 review 一个 spring service 改动"))
    runtime = initialize_runtime(ROOT, manifest, task_statement="帮我 review 一个 spring service 改动", runtime_id="runtime.claude-code-test")
    return prepare_adapter_request(ROOT, runtime)


def _request():
    runtime = _prepared_runtime()
    bundle = build_context_bundle(ROOT, runtime, bundle_id="context_bundle.claude-code-test")
    return runtime, bundle, build_claude_code_host_request(ROOT, runtime, bundle, request_id="claude_code_request.test")


def _result(request, status="succeeded"):
    result = deepcopy(request["result_contract"]["result_skeleton"])
    result["status"] = status
    result["metadata"] = {"host": "claude_code"}
    return result


def test_claude_code_request_preserves_bundle_order_and_validates():
    _, bundle, request = _request()

    assert validate_claude_code_host_request(ROOT, request) == []
    stable = next(segment for segment in request["prompt"]["segments"] if segment["kind"] == "stable_instruction")
    module_ids = [module["id"] for layer in bundle["layers"] for module in layer["modules"]]
    positions = [stable["content"].index(f"id={module_id} ") for module_id in module_ids]
    assert positions == sorted(positions)
    assert request["runtime"]["stage_id"] == "engine.discover"
    assert request["prompt"]["task_prompt_digest"].startswith("sha256:")


def test_claude_code_request_fails_closed_on_bundle_and_runtime_tampering():
    runtime, bundle, _ = _request()
    tampered_bundle = deepcopy(bundle)
    tampered_bundle["layers"][0]["modules"][0]["content"] += "tampered"
    with pytest.raises(ValueError, match="BUNDLE_DIGEST_MISMATCH"):
        build_claude_code_host_request(ROOT, runtime, tampered_bundle)

    tampered_runtime = deepcopy(runtime)
    tampered_runtime["resolved_context"]["selection"]["skill"] = "skill.debug"
    with pytest.raises(ValueError, match="MANIFEST_DIGEST_MISMATCH"):
        build_claude_code_host_request(ROOT, tampered_runtime, bundle)


def test_claude_code_result_normalizes_for_existing_import():
    runtime, _, request = _request()

    normalized = validate_and_normalize_claude_code_host_result(ROOT, request, _result(request))
    imported = import_adapter_result(ROOT, runtime, normalized)
    assert imported["status"] == "result_imported"
    assert imported["adapter_result"]["adapter_id"] == "forge.claude_code_host"


@pytest.mark.parametrize("status", ["failed", "blocked", "skipped"])
def test_claude_code_result_accepts_generic_terminal_statuses(status):
    _, _, request = _request()
    assert validate_and_normalize_claude_code_host_result(ROOT, request, _result(request, status))["status"] == status


def test_claude_code_result_rejects_linkage_mismatch():
    _, _, request = _request()
    result = _result(request)
    result["linkage"]["context_bundle_digest"] = canonical_digest({"wrong": True})

    with pytest.raises(ValueError, match="RESULT_LINK_MISMATCH"):
        validate_and_normalize_claude_code_host_result(ROOT, request, result)
