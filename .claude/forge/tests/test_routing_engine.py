# -*- coding: utf-8 -*-
"""Tests for forge_cli.routing_engine — skill/pack routing, merge, compose."""

import json
from pathlib import Path

import pytest

from forge_cli.cli import _execute_route, _build_ask_decision, _is_forge_first_skill, _match_native_first
from forge_cli.route_regression import evaluate_regression_case, load_regression_cases
from forge_cli.routing_engine import (
    _build_prefer_fallback,
    _resolve_skill_variant,
    build_recommendation_from_route,
    compose_selection,
    merge_skill_and_pack_route,
    route_by_skill_triggers,
    route_pack,
    score_pack_match,
)


REAL_FORGE_ROOT = Path(__file__).resolve().parents[1]
REGRESSION_CASES = load_regression_cases(REAL_FORGE_ROOT)


class TestRealRegistryRouteRegression:
    @pytest.mark.parametrize("case", REGRESSION_CASES, ids=lambda case: case["id"])
    def test_canonical_case_matches_real_registry(self, case):
        if case["mode"] == "ask":
            text = case["input"]
            if text.startswith("/"):
                result = _build_ask_decision(
                    text,
                    reason_code="explicit_skill",
                    decision="explicit_skill_passthrough",
                )
            else:
                native = _match_native_first(REAL_FORGE_ROOT, text)
                if native:
                    result = _build_ask_decision(
                        text,
                        reason_code=native["reason_code"],
                        reason_detail=native["id"],
                        native=native,
                    )
                else:
                    route_result = _execute_route(REAL_FORGE_ROOT, text, case.get("preferred_skill"))
                    result = _build_ask_decision(
                        text,
                        route_result if route_result.get("matched") and _is_forge_first_skill(REAL_FORGE_ROOT, route_result) else None,
                        reason_code="forge_skill_matched" if route_result.get("matched") else "no_forge_match",
                    )
        else:
            route_result = _execute_route(REAL_FORGE_ROOT, case["input"], case.get("preferred_skill"))
            result = route_result if case["mode"] == "route" else build_recommendation_from_route(route_result)
        evaluation = evaluate_regression_case(case, result)
        assert evaluation["passed"], (
            f"{case['id']}: input={case['input']!r}; "
            f"actual={evaluation['actual']}; errors={evaluation['errors']}"
        )


class TestRouteProjectionProperties:
    @pytest.mark.parametrize("case", [case for case in REGRESSION_CASES if case["mode"] != "ask"], ids=lambda case: case["id"])
    def test_route_and_recommendation_preserve_selection_contract(self, case):
        route = _execute_route(REAL_FORGE_ROOT, case["input"], case.get("preferred_skill"))
        recommendation = build_recommendation_from_route(route)

        assert recommendation["matched"] is route["matched"]
        assert recommendation["confidence"] == route["confidence"]
        assert recommendation.get("confidence_diagnostics") == route.get("confidence_diagnostics")
        if route["matched"]:
            selected = recommendation["recommended"]
            assert selected["skill"] == route["skill"]["id"]
            assert selected["variant"] == route.get("variant")
            assert selected["pack"] == (route.get("pack") or {}).get("id")
            assert selected["domains"] == route["domains"]

    @pytest.mark.parametrize("case", [case for case in REGRESSION_CASES if case["mode"] != "ask"], ids=lambda case: case["id"])
    def test_route_is_deterministic_for_real_regression_corpus(self, case):
        first = _execute_route(REAL_FORGE_ROOT, case["input"], case.get("preferred_skill"))
        second = _execute_route(REAL_FORGE_ROOT, case["input"], case.get("preferred_skill"))

        assert first == second

    def test_review_route_exposes_ranked_candidates(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "帮我 review spring 代码")
        assert result["matched"] is True
        assert result["candidates"]
        scores = [candidate["score"] for candidate in result["candidates"]]
        assert scores == sorted(scores, reverse=True)

    def test_pack_merge_exposes_pack_evidence(self, populated_forge_root):
        skill_route = route_by_skill_triggers(populated_forge_root, "review spring service")
        pack_route = route_pack(populated_forge_root, "review spring service", skill_route["skill"]["id"])
        merged = merge_skill_and_pack_route(skill_route, pack_route)
        assert merged["pack"]["id"] == "pack.test_pack"
        assert merged["pack_evidence"]
        evidence_types = {item["type"] for item in merged["pack_evidence"]}
        assert "pack_keyword_any" in evidence_types or "pack_keyword_group" in evidence_types
    def test_matches_review_input(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "帮我 review 这个代码")
        assert result["matched"] is True
        assert result["skill"]["id"] == "skill.code_review"
        assert result["confidence"] in ("high", "medium", "low")

    def test_matches_debug_input(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "排查这个生产问题")
        assert result["matched"] is True
        assert result["skill"]["id"] == "skill.debug"

    def test_no_match_returns_unmatched(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "xyzzy nothing matches")
        assert result["matched"] is False
        assert result["confidence"] == "low"
        assert result["reason"] is not None
        diagnostics = result["confidence_diagnostics"]
        assert diagnostics["selection_mode"] == "unmatched"
        assert diagnostics["base_confidence"] == diagnostics["final_confidence"] == "low"
        assert diagnostics["candidate_count"] == 0
        assert diagnostics["caps"] == ["unmatched"]

    def test_empty_input(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "")
        assert result["matched"] is False

    def test_returns_expected_fields(self, populated_forge_root):
        result = route_by_skill_triggers(populated_forge_root, "帮我 review")
        assert "input" in result
        assert "strategy" in result
        assert "confidence" in result
        assert "skill" in result
        assert "candidates" in result
        assert "matched_triggers" in result


class TestScorePackMatch:
    def test_matches_on_keywords(self):
        pack = {
            "id": "pack.test",
            "name": "Test",
            "routing": {
                "preferred_skill": "skill.code_review",
                "keywords_any": ["spring", "review"],
                "score_bonus": 10,
            },
        }
        result = score_pack_match("review this spring code", pack)
        assert result["matched"] is True
        assert result["score"] > 0
        assert len(result["evidence"]) > 0

    def test_no_match_without_keywords(self):
        pack = {
            "id": "pack.test",
            "name": "Test",
            "routing": {
                "preferred_skill": "skill.code_review",
                "keywords_any": ["spring", "java"],
                "keywords_all_groups": [["nonexistent_word"]],
                "score_bonus": 10,
            },
        }
        result = score_pack_match("debug this python code", pack)
        assert result["matched"] is False

    def test_no_routing_rule_returns_unmatched(self):
        pack = {"id": "pack.test", "name": "Test"}
        result = score_pack_match("anything", pack)
        assert result["matched"] is False
        assert result["reason"] is not None


class TestRoutePack:
    def test_finds_matching_pack(self, populated_forge_root):
        result = route_pack(populated_forge_root, "review the spring service")
        assert result is not None
        assert result["matched"] is True

    def test_no_match_returns_none(self, populated_forge_root):
        result = route_pack(populated_forge_root, "xyzzy nothing")
        assert result is None




class TestSkillVariantResolution:
    def test_variant_replaces_declared_domains(self):
        skill = {
            "domains": ["domain.java"],
            "workflow": "workflow.full_default",
            "variants": [{
                "type": "vue_transition",
                "selection": {"keyword_sets_any": ["transition"], "priority": 1},
                "domains": ["domain.vue2", "domain.vue2_7"],
            }],
        }
        result = _resolve_skill_variant(skill, {"transition_hits": ["vue 2 -> vue 2.7"]})
        assert result["variant"] == "vue_transition"
        assert result["composition"]["domains"] == ["domain.vue2", "domain.vue2_7"]
        assert result["composition"]["workflow"] == "workflow.full_default"

    def test_ambiguous_variants_fall_back_to_base_composition(self):
        skill = {
            "domains": ["domain.java"],
            "variants": [
                {"type": "first", "selection": {"keyword_sets_any": ["transition"], "priority": 1}, "domains": ["domain.vue2"]},
                {"type": "second", "selection": {"keyword_sets_any": ["transition"], "priority": 1}, "domains": ["domain.vue3_vite"]},
            ],
        }
        result = _resolve_skill_variant(skill, {"transition_hits": ["upgrade"]})
        assert result["variant"] is None
        assert result["composition"]["domains"] == ["domain.java"]
        assert result["warnings"]


    def test_merge_with_pack(self, populated_forge_root):
        skill_route = route_by_skill_triggers(populated_forge_root, "帮我 review spring 代码")
        pack_route = route_pack(populated_forge_root, "review spring", skill_route["skill"]["id"])
        merged = merge_skill_and_pack_route(skill_route, pack_route)
        assert merged["matched"] is True
        assert "skill+pack" in merged["strategy"]
        assert merged["pack"] is not None

    def test_merge_without_pack(self, populated_forge_root):
        skill_route = route_by_skill_triggers(populated_forge_root, "帮我 review")
        merged = merge_skill_and_pack_route(skill_route, None)
        assert merged["matched"] is True
        assert merged["pack"] is None

    def test_unmatched_skill_unchanged(self, populated_forge_root):
        skill_route = route_by_skill_triggers(populated_forge_root, "xyzzy")
        merged = merge_skill_and_pack_route(skill_route, None)
        assert merged["matched"] is False


class TestBuildRecommendationFromRoute:
    def test_matched_route(self, populated_forge_root):
        skill_route = route_by_skill_triggers(populated_forge_root, "帮我 review 代码")
        result = build_recommendation_from_route(skill_route)
        assert result["matched"] is True
        assert result["mode"] == "recommend"
        assert result["recommended"] is not None
        assert result["recommended"]["skill"] == "skill.code_review"

    def test_unmatched_route(self):
        route = {"matched": False, "input": "xyzzy", "confidence": "low",
                 "reason": "No match"}
        result = build_recommendation_from_route(route)
        assert result["matched"] is False
        assert result["recommended"] is None


class TestPreferFallback:
    def test_valid_skill(self, populated_forge_root):
        result = _build_prefer_fallback(populated_forge_root, "do something", "code-review")
        assert result is not None
        assert result["matched"] is True
        assert result["skill"]["id"] == "skill.code_review"
        assert result["confidence"] == "low"
        diagnostics = result["confidence_diagnostics"]
        assert diagnostics["selection_mode"] == "prefer_fallback"
        assert diagnostics["base_confidence"] == diagnostics["final_confidence"] == "low"
        assert diagnostics["caps"] == ["fallback"]

    def test_invalid_skill(self, populated_forge_root):
        result = _build_prefer_fallback(populated_forge_root, "do something", "nonexistent")
        assert result is None


class TestComposeSelection:
    def test_with_skill(self, populated_forge_root):
        result = compose_selection(populated_forge_root, skill_query="code-review")
        assert result["matched"] is True
        assert result["skill"] == "skill.code_review"
        assert result["behavior"] == "behavior.review"
        assert result["template"] == "template.review_report"

    def test_cli_overrides(self, populated_forge_root):
        result = compose_selection(
            populated_forge_root,
            skill_query="code-review",
            behavior="behavior.debug",
            template="template.debug_report",
        )
        assert result["behavior"] == "behavior.debug"
        assert result["sources"]["behavior"] == "cli"
        assert result["template"] == "template.debug_report"

    def test_domain_merge(self, populated_forge_root):
        result = compose_selection(
            populated_forge_root,
            skill_query="code-review",
            domains=["domain.spring"],
        )
        assert "domain.java" in result["domains"]
        assert "domain.spring" in result["domains"]
        assert "cli" in result["sources"]["domains"]

    def test_unresolved_skill_query_records_warning(self, populated_forge_root):
        result = compose_selection(populated_forge_root, skill_query="nonexistent")
        assert result["matched"] is True
        assert result["skill"] is None
        assert result["unresolved"]["skill"] == "nonexistent"
        assert any("Requested skill not found" in msg for msg in result["warnings"])

    def test_unresolved_pack_query_records_warning(self, populated_forge_root):
        result = compose_selection(populated_forge_root, pack_query="nonexistent")
        assert result["matched"] is True
        assert result["pack"] is None
        assert result["unresolved"]["pack"] == "nonexistent"
        assert any("Requested pack not found" in msg for msg in result["warnings"])
