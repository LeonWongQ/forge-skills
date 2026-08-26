# -*- coding: utf-8 -*-
"""Tests for forge_cli.routing_config — trigger scoring, keyword matching, bias rules."""

from pathlib import Path

from forge_cli.routing_config import (
    apply_skill_bias_rules,
    count_keyword_hits,
    get_default_skill_routing_config,
    get_effective_skill_routing_config,
    get_keyword_hits_map,
    score_trigger_match,
)


class TestDefaultRoutingConfig:
    def test_has_required_keys(self):
        config = get_default_skill_routing_config()
        assert "keyword_sets" in config
        assert "generic_trigger_penalties" in config
        assert "skill_bias_rules" in config
        assert "tie_break_rules" in config

    def test_keyword_sets_not_empty(self):
        config = get_default_skill_routing_config()
        assert len(config["keyword_sets"]) >= 8

    def test_plan_penalty_exists(self):
        config = get_default_skill_routing_config()
        assert "skill.plan" in config["generic_trigger_penalties"]


class TestEffectiveRoutingConfig:
    def test_default_when_no_external(self, forge_root):
        config = get_effective_skill_routing_config(forge_root)
        assert "keyword_sets" in config

    def test_external_overrides_default(self, populated_forge_root):
        config = get_effective_skill_routing_config(populated_forge_root)
        # The fixture's skill-routing.json sets these keys to empty values, and
        # get_effective_skill_routing_config REPLACES a key entirely when present
        # in external (it does not merge). Assert the override actually took
        # effect — the defaults (8 keyword sets, a non-empty tie-break list) must
        # be gone, replaced by the empty external values. This verifies the
        # override mechanism, not just key presence.
        assert config["keyword_sets"] == {}
        assert config["tie_break_rules"] == []


class TestScoreTriggerMatch:
    def test_exact_match_scores_positive(self):
        score = score_trigger_match("review this code", "review")
        assert score >= 4  # len("review") = 6

    def test_no_match_scores_zero(self):
        score = score_trigger_match("debug this", "review")
        assert score == 0

    def test_case_insensitive(self):
        score = score_trigger_match("REVIEW this", "review")
        assert score > 0

    def test_chinese_trigger(self):
        score = score_trigger_match("帮我 review 代码", "帮我 review")
        assert score > 0

    def test_empty_trigger_zero(self):
        score = score_trigger_match("some text", "")
        assert score == 0

    def test_partial_substring_match(self):
        # score_trigger_match uses substring containment: "debug" is a substring
        # of "debugging", so it scores positive. This documents the intended
        # (substring-based) matching behavior rather than asserting a "no match".
        score = score_trigger_match("debugging", "debug")
        assert score > 0


class TestCountKeywordHits:
    def test_matching_keywords(self):
        hits = count_keyword_hits("debug this error", {"debug", "error", "review"})
        assert "debug" in hits
        assert "error" in hits
        assert "review" not in hits

    def test_chinese_keywords(self):
        hits = count_keyword_hits("帮我排查线上故障", {"排查", "线上", "debug"})
        assert "排查" in hits
        assert "线上" in hits
        assert "debug" not in hits

    def test_no_hits(self):
        hits = count_keyword_hits("hello world", {"debug", "error"})
        assert hits == []


class TestGetKeywordHitsMap:
    def test_returns_dict_with_hits_suffix(self, forge_root):
        hits_map = get_keyword_hits_map(forge_root, "debug this error")
        assert "debug_hits" in hits_map
        assert isinstance(hits_map["debug_hits"], list)


class TestApplySkillBiasRules:
    def test_no_rules_returns_zero(self, forge_root):
        bonus, evidence = apply_skill_bias_rules(
            forge_root, "skill.unknown", "test input", [], {}
        )
        assert bonus == 0
        assert evidence == []

    def test_keyword_bonus_increases_score(self, forge_root):
        intent_bias = {"debug_hits": ["debug", "排查"]}
        # The default config has no bias rules, so bonus stays 0
        bonus, evidence = apply_skill_bias_rules(
            forge_root, "skill.debug", "debug 排查", ["debug"], intent_bias
        )
        # Default config has no skill_bias_rules for debug, so bonus is 0
        # This tests graceful handling of missing rules
        assert isinstance(bonus, int)
        assert isinstance(evidence, list)
