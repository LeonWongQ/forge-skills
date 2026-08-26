# -*- coding: utf-8 -*-
"""Forge CLI — skill routing configuration: trigger scoring, keyword matching, bias rules."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .constants import (
    DEBUG_KEYWORDS,
    ERROR_ANALYSIS_KEYWORDS,
    GENERIC_PLAN_TRIGGERS,
    INCIDENT_KEYWORDS,
    MIGRATION_KEYWORDS,
    PLAN_KEYWORDS,
    REFACTOR_KEYWORDS,
    TEST_DESIGN_KEYWORDS,
    TEST_IMPLEMENTATION_KEYWORDS,
)
from .helpers import normalize_text
from .registry_discovery import load_skill_routing_config


def get_default_skill_routing_config() -> Dict[str, Any]:
    return {
        "keyword_sets": {
            "test_design": list(TEST_DESIGN_KEYWORDS),
            "test_implementation": list(TEST_IMPLEMENTATION_KEYWORDS),
            "plan": list(PLAN_KEYWORDS),
            "migration": list(MIGRATION_KEYWORDS),
            "refactor": list(REFACTOR_KEYWORDS),
            "incident": list(INCIDENT_KEYWORDS),
            "error_analysis": list(ERROR_ANALYSIS_KEYWORDS),
            "debug": list(DEBUG_KEYWORDS),
        },
        "generic_trigger_penalties": {
            "skill.plan": list(GENERIC_PLAN_TRIGGERS)
        },
        "skill_bias_rules": {},
        "tie_break_rules": [],
        "confidence_policy": {
            "version": "v1", "single_candidate_max": "medium", "keyword_only_max": "low",
            "tie_break_max": "medium", "fallback_confidence": "low",
            "ordinary_gap_low_max": 2, "ordinary_gap_medium_max": 5, "pack_can_promote": False,
        },
        "ask_policy": {
            "version": "v2",
            "ownership_order": ["runtime", "explicit_skill", "native_first", "forge_first", "native_fallback"],
            "forge_first_skills": [
                "skill.code_review", "skill.plan", "skill.explore", "skill.debug",
                "skill.implement", "skill.refactor", "skill.optimize", "skill.dependency_audit",
                "skill.test_design", "skill.test_implementation", "skill.test_strategy", "skill.page_test",
                "skill.incident", "skill.error_analysis", "skill.release_readiness", "skill.contract_compatibility",
                "skill.architecture_design", "skill.security_review", "skill.data_design",
                "skill.document", "skill.report", "skill.explain", "skill.migration",
                "skill.vite_vue3", "skill.vue2", "skill.vue2_7"
            ],
            "native_first": [
                {"id": "native.claude_api", "skill": "claude-api", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["claude api", "anthropic api", "anthropic sdk", "claude sdk", "mcp", "mcp server", "mcp tool", "prompt caching", "tool use", "agent sdk"]},
                {"id": "native.run", "skill": "run", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["运行应用", "启动应用", "start the app", "run the app", "截图应用", "screenshot the app"]},
                {"id": "native.update_config", "skill": "update-config", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["settings.json", "claude code hook", "claude code 权限", "permissions", "hooks", "环境变量", "environment variable"]},
                {"id": "native.review", "skill": "review", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["github pr", "pull request", "github review", "github pull request"]},
                {"id": "native.deep_research", "skill": "deep-research", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["深度研究", "多来源研究", "deep research", "multi-source research", "fact-check"]},
                {"id": "native.dataviz", "skill": "dataviz", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["数据可视化", "chart", "graph", "dashboard", "visualization"]},
                {"id": "native.loop", "skill": "loop", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["每隔", "定时", "循环执行", "every day", "every week", "every hour", "every minute", "run this every", "recurring", "schedule this"]},
                {"id": "native.keybindings_help", "skill": "keybindings-help", "invocation": "skill", "reason_code": "native_specialist_matched", "triggers": ["keybindings", "快捷键", "keybindings.json", "keyboard shortcut"]}
            ]
        },
    }


def get_effective_skill_routing_config(root: Path) -> Dict[str, Any]:
    config = get_default_skill_routing_config()
    external = load_skill_routing_config(root)

    for key in ("keyword_sets", "generic_trigger_penalties", "skill_bias_rules", "tie_break_rules", "confidence_policy", "ask_policy"):
        if key in external:
            config[key] = external[key]

    return config


def get_generic_trigger_penalties(root: Path) -> Dict[str, List[str]]:
    config = get_effective_skill_routing_config(root)
    penalties = config.get("generic_trigger_penalties")
    if isinstance(penalties, dict):
        return penalties
    return {
        "skill.plan": list(GENERIC_PLAN_TRIGGERS)
    }


def score_trigger_match(text: str, trigger: str, skill_id: Optional[str] = None, root: Optional[Path] = None) -> int:
    t = normalize_text(text)
    trg = normalize_text(trigger)

    if not trg:
        return 0

    if trg not in t:
        return 0

    base = max(1, len(trg))

    if skill_id and root is not None:
        generic_penalties = get_generic_trigger_penalties(root)
        penalized_triggers = set(generic_penalties.get(skill_id, []))
        if trigger in penalized_triggers:
            return 1

    return base


def count_keyword_hits(text: str, keywords: Set[str]) -> List[str]:
    t = normalize_text(text)
    hits = []
    for kw in keywords:
        if normalize_text(kw) in t:
            hits.append(kw)
    return sorted(set(hits))


def get_keyword_hits_map(root: Path, text: str) -> Dict[str, List[str]]:
    config = get_effective_skill_routing_config(root)
    keyword_sets = config.get("keyword_sets", {})
    result = {}

    if isinstance(keyword_sets, dict):
        for name, values in keyword_sets.items():
            if isinstance(values, list):
                result[f"{name}_hits"] = count_keyword_hits(text, set(v for v in values if isinstance(v, str)))

    return result


def apply_skill_bias_rules(
    root: Path,
    skill_id: str,
    user_input: str,
    matched_triggers: List[str],
    intent_bias: Dict[str, List[str]],
) -> Tuple[int, List[Dict[str, Any]]]:
    config = get_effective_skill_routing_config(root)
    rules = config.get("skill_bias_rules", {})
    rule = rules.get(skill_id, {})

    keyword_bonus = 0
    keyword_evidence = []

    for item in rule.get("keyword_bonus", []):
        keyword_set = item.get("keyword_set")
        weight = item.get("weight", 0)
        evidence_type = item.get("evidence_type", "keyword_bonus")
        hits = intent_bias.get(f"{keyword_set}_hits", [])
        if hits:
            keyword_bonus += weight * len(hits)
            keyword_evidence.extend([{"type": evidence_type, "value": x} for x in hits])

    for item in rule.get("keyword_penalty", []):
        keyword_set = item.get("keyword_set")
        weight = item.get("weight", 0)
        evidence_type = item.get("evidence_type", "keyword_penalty")
        hits = intent_bias.get(f"{keyword_set}_hits", [])
        if hits:
            keyword_bonus -= weight
            keyword_evidence.extend([{"type": evidence_type, "value": x} for x in hits])

    if matched_triggers:
        for item in rule.get("keyword_penalty_when_trigger_matched", []):
            keyword_set = item.get("keyword_set")
            weight = item.get("weight", 0)
            evidence_type = item.get("evidence_type", "keyword_penalty")
            hits = intent_bias.get(f"{keyword_set}_hits", [])
            if hits:
                keyword_bonus -= weight
                keyword_evidence.extend([{"type": evidence_type, "value": x} for x in hits])

    for item in rule.get("keyword_penalty_when_absent", []):
        required_set = item.get("required_set")
        keyword_set = item.get("keyword_set")
        weight = item.get("weight", 0)
        evidence_type = item.get("evidence_type", "keyword_penalty")

        required_hits = intent_bias.get(f"{required_set}_hits", [])
        hits = intent_bias.get(f"{keyword_set}_hits", [])
        if hits and not required_hits:
            keyword_bonus -= weight
            keyword_evidence.extend([{"type": evidence_type, "value": x} for x in hits])

    postmortem_hint_bonus = rule.get("postmortem_hint_bonus")
    if isinstance(postmortem_hint_bonus, dict):
        requires_keyword_set = postmortem_hint_bonus.get("requires_keyword_set")
        text_any = postmortem_hint_bonus.get("text_any", [])
        weight = postmortem_hint_bonus.get("weight", 0)
        evidence_type = postmortem_hint_bonus.get("evidence_type", "special_bonus")

        required_hits = intent_bias.get(f"{requires_keyword_set}_hits", []) if requires_keyword_set else []
        normalized_input = normalize_text(user_input)

        if required_hits and any(normalize_text(x) in normalized_input for x in text_any if isinstance(x, str)):
            keyword_bonus += weight
            keyword_evidence.append({"type": evidence_type, "value": "special_text_hint"})

    return keyword_bonus, keyword_evidence
