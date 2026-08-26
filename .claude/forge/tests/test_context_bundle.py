# -*- coding: utf-8 -*-
"""Tests for safe, deterministic inline Context Bundle materialization."""

from pathlib import Path

import pytest

from forge_cli.cli import _execute_route
from forge_cli.context_bundle import build_context_bundle, estimate_tokens
from forge_cli.resolved_context import build_context_from_route
from forge_cli.runtime_composition import initialize_runtime
from forge_cli.runtime_contracts import CONTEXT_BUNDLE_LAYER_ORDER, canonical_digest, validate_context_bundle


ROOT = Path(__file__).resolve().parents[1]


def _envelope():
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "帮我 review 一个 spring service 改动"))
    return initialize_runtime(ROOT, manifest, task_statement="帮我 review 一个 spring service 改动", runtime_id="runtime.bundle-test")


def _digest_projection(bundle):
    payload = dict(bundle)
    payload.pop("bundle_digest")
    return canonical_digest(payload)


def test_context_bundle_materializes_ordered_utf8_content():
    bundle = build_context_bundle(ROOT, _envelope(), bundle_id="context_bundle.test")

    assert validate_context_bundle(ROOT, bundle) == []
    layer_ids = [layer["id"] for layer in bundle["layers"]]
    assert layer_ids == [layer for layer in CONTEXT_BUNDLE_LAYER_ORDER if layer in layer_ids and layer not in {"workflow", "packs"}]
    kernel = bundle["layers"][0]["modules"][0]
    assert kernel["id"] == "kernel.claude"
    assert "modular AI engineering assistant" in kernel["content"]
    assert kernel["byte_size"] == len(kernel["content"].encode("utf-8"))
    assert bundle["bundle_digest"] == _digest_projection(bundle)
    assert bundle["workflow"]["id"] == "workflow.full_default"


def test_context_bundle_fails_closed_on_tampered_manifest_digest():
    envelope = _envelope()
    envelope["resolved_context"]["selection"]["skill"] = "skill.debug"

    with pytest.raises(ValueError, match="MANIFEST_DIGEST_MISMATCH"):
        build_context_bundle(ROOT, envelope)


def test_context_bundle_enforces_byte_limits():
    with pytest.raises(ValueError, match="MODULE_TOO_LARGE"):
        build_context_bundle(ROOT, _envelope(), max_module_bytes=1)
    with pytest.raises(ValueError, match="TOO_LARGE"):
        build_context_bundle(ROOT, _envelope(), max_bundle_bytes=1)


def test_context_bundle_can_enforce_an_auditable_estimated_token_budget():
    envelope = _envelope()
    full_bundle = build_context_bundle(ROOT, envelope)
    first_module = full_bundle["layers"][0]["modules"][0]
    budget = estimate_tokens(first_module["content"])

    bundle = build_context_bundle(ROOT, envelope, max_estimated_tokens=budget)

    assert validate_context_bundle(ROOT, bundle) == []
    assert bundle["budget"]["max_estimated_tokens"] == budget
    assert bundle["budget"]["included_estimated_tokens"] == budget
    assert bundle["layers"][0]["modules"][0]["id"] == first_module["id"]
    assert bundle["budget"]["skipped_modules"]
    assert all(item["reason"] == "estimated_token_budget_exceeded" for item in bundle["budget"]["skipped_modules"])


def test_context_bundle_rejects_manifest_path_assertion_mismatch():
    envelope = _envelope()
    envelope["resolved_context"]["context"]["kernel"][0]["resolved_path"] = ".claude/forge/other.md"
    envelope["resolved_context_digest"] = canonical_digest(envelope["resolved_context"])

    with pytest.raises(ValueError, match="PATH_MISMATCH"):
        build_context_bundle(ROOT, envelope)


def test_context_bundle_uses_the_active_codex_prefix(tmp_path):
    forge_root = tmp_path / ".codex" / "forge"
    source = ROOT / "CLAUDE.md"
    target = forge_root / "CLAUDE.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())

    from forge_cli.context_bundle import _portable_path

    assert _portable_path(forge_root, target) == ".codex/forge/CLAUDE.md"
