# -*- coding: utf-8 -*-
"""Tests for conservative evidence-based runtime domain selection."""

from pathlib import Path

from forge_cli.domain_resolution import resolve_domains


ROOT = Path(__file__).resolve().parents[1]


def test_request_evidence_narrows_eligible_domains():
    result = resolve_domains(
        ROOT,
        ["domain.java", "domain.spring", "domain.redis", "domain.testing", "domain.vue2"],
        "review a Spring service",
    )

    assert result["selected_domains"] == ["domain.spring"]
    assert result["confidence"] == "medium"


def test_artifact_evidence_activates_related_domain_only_with_corroboration():
    result = resolve_domains(
        ROOT,
        ["domain.spring"],
        "review Spring caching",
        ["RedisTemplate", "cache invalidation code"],
    )

    assert result["selected_domains"] == ["domain.spring", "domain.redis"]
    assert any(item["domain_id"] == "domain.redis" and item["accepted"] for item in result["related_candidates"])


def test_protected_domains_survive_missing_direct_evidence():
    result = resolve_domains(ROOT, ["domain.java", "domain.redis"], "review this", protected_domains=["domain.java"])

    assert result["selected_domains"] == ["domain.java"]
    assert result["rejected"] == [{"domain_id": "domain.redis", "reason": "no_direct_evidence"}]


def test_no_evidence_uses_explicit_conservative_fallback():
    result = resolve_domains(ROOT, ["domain.java", "domain.redis"], "review this")

    assert result["selected_domains"] == ["domain.java", "domain.redis"]
    assert result["confidence"] == "low"
    assert result["warnings"]
