# -*- coding: utf-8 -*-
"""Forge CLI — routing engine: skill/pack matching, merge, compose, recommendation."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .constants import PACK_CROSS_SKILL_ALLOWED
from .query_helpers import (
    contains_any,
    find_pack_object_by_id,
    find_pack_by_query,
    find_skill_by_query,
    match_all_keyword_groups,
)
from .registry_discovery import load_array_registry, load_pack_objects
from .routing_config import (
    apply_skill_bias_rules,
    get_effective_skill_routing_config,
    get_keyword_hits_map,
    score_trigger_match,
)


CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def _confidence_diagnostics(
    policy: Dict[str, Any],
    *,
    base_confidence: str,
    final_confidence: str,
    selection_mode: str,
    candidate_count: int,
    runner_up_score: Optional[int],
    margin: Optional[int],
    matched_trigger_count: int,
    keyword_evidence_count: int,
    caps: List[str],
) -> Dict[str, Any]:
    """Build the stable explainability payload for all route outcomes."""
    return {
        "policy_version": policy.get("version"),
        "base_confidence": base_confidence,
        "final_confidence": final_confidence,
        "selection_mode": selection_mode,
        "candidate_count": candidate_count,
        "runner_up_score": runner_up_score,
        "margin": margin,
        "matched_trigger_count": matched_trigger_count,
        "keyword_evidence_count": keyword_evidence_count,
        "caps": caps,
        "pack_promotion": "not_applied",
    }


def _resolve_skill_variant(skill: Dict[str, Any], intent_bias: Dict[str, List[str]]) -> Dict[str, Any]:
    """Select an opt-in variant and apply its declared composition overrides."""
    composition = {
        "behavior": skill.get("behavior"),
        "workflow": skill.get("workflow"),
        "domains": skill.get("domains", []),
        "template": skill.get("template"),
        "checklists": skill.get("checklists", []),
    }
    matches = []
    for variant in skill.get("variants", []):
        if not isinstance(variant, dict) or not isinstance(variant.get("selection"), dict):
            continue
        selection = variant["selection"]
        keyword_sets = selection.get("keyword_sets_any", [])
        hits = []
        for keyword_set in keyword_sets:
            for value in intent_bias.get(f"{keyword_set}_hits", []):
                hits.append({"type": "variant_keyword", "keyword_set": keyword_set, "value": value})
        if hits:
            matches.append((selection.get("priority", 0), variant, hits))

    if not matches:
        return {"variant": None, "composition": composition, "evidence": [], "warnings": []}

    highest_priority = max(priority for priority, _, _ in matches)
    finalists = [(variant, hits) for priority, variant, hits in matches if priority == highest_priority]
    if len(finalists) != 1:
        return {
            "variant": None,
            "composition": composition,
            "evidence": [],
            "warnings": ["Ambiguous skill variant selectors; using base skill composition"],
        }

    variant, evidence = finalists[0]
    for field in ("behavior", "domains", "template", "checklists"):
        if field in variant:
            composition[field] = variant[field]
    return {
        "variant": variant.get("type"),
        "composition": composition,
        "evidence": evidence,
        "warnings": [],
    }


def route_by_skill_triggers(root: Path, user_input: str) -> Dict[str, Any]:
    skills = load_array_registry(root, "skills.json", ["skills"])
    scored_matches: List[Dict[str, Any]] = []
    intent_bias = get_keyword_hits_map(root, user_input)

    for skill in skills:
        if not isinstance(skill, dict):
            continue

        skill_id = skill.get("id")
        triggers = skill.get("triggers", [])
        if not isinstance(triggers, list):
            continue

        matched_triggers = []
        trigger_score = 0

        for trigger in triggers:
            if not isinstance(trigger, str):
                continue
            score = score_trigger_match(user_input, trigger, skill_id=skill_id, root=root)
            if score > 0:
                matched_triggers.append(trigger)
                trigger_score += score

        keyword_bonus, keyword_evidence = apply_skill_bias_rules(
            root=root,
            skill_id=skill_id,
            user_input=user_input,
            matched_triggers=matched_triggers,
            intent_bias=intent_bias,
        )

        total_score = trigger_score + keyword_bonus

        if total_score > 0:
            scored_matches.append({
                "skill": skill,
                "skill_id": skill_id,
                "trigger_score": trigger_score,
                "keyword_bonus": keyword_bonus,
                "total_score": total_score,
                "matched_triggers": matched_triggers,
                "evidence": keyword_evidence,
            })

    if not scored_matches:
        policy = get_effective_skill_routing_config(root).get("confidence_policy", {})
        confidence = "low"
        return {
            "matched": False,
            "input": user_input,
            "strategy": "skill-trigger-v6",
            "reason": "No skill trigger matched input",
            "confidence": confidence,
            "confidence_diagnostics": _confidence_diagnostics(
                policy,
                base_confidence=confidence,
                final_confidence=confidence,
                selection_mode="unmatched",
                candidate_count=0,
                runner_up_score=None,
                margin=None,
                matched_trigger_count=0,
                keyword_evidence_count=0,
                caps=["unmatched"],
            ),
            "skill": None,
            "behavior": None,
            "workflow": None,
            "domains": [],
            "template": None,
            "checklists": [],
            "matched_triggers": [],
            "evidence": [],
            "candidates": [],
        }

    sorted_matches = sorted(scored_matches, key=lambda x: x["total_score"], reverse=True)
    best = sorted_matches[0]
    second = sorted_matches[1] if len(sorted_matches) > 1 else None

    original_score_gap = best["total_score"] - second["total_score"] if second else None
    config = get_effective_skill_routing_config(root)
    tie_break_rules = config.get("tie_break_rules", [])
    tie_break_applied = False

    if second:
        best_id = best["skill_id"]
        second_id = second["skill_id"]
        score_gap = best["total_score"] - second["total_score"]
        top_two = {best_id, second_id}

        for rule in tie_break_rules:
            skills_pair = set(rule.get("skills", []))
            max_gap = rule.get("max_gap", 0)
            prefer_if_set_present = rule.get("prefer_if_set_present")
            avoid_if_set_present = rule.get("avoid_if_set_present")

            if top_two == skills_pair and score_gap <= max_gap:
                prefer_hits = intent_bias.get(f"{prefer_if_set_present}_hits", []) if prefer_if_set_present else []
                avoid_hits = intent_bias.get(f"{avoid_if_set_present}_hits", []) if avoid_if_set_present else []

                if prefer_hits and (not avoid_hits or avoid_if_set_present is None):
                    preferred_skill_id = None

                    # Deterministic exact match first: "implement" -> "skill.implement".
                    # A substring match ("prefer" in "skill.xxx") is ambiguous when the
                    # preference token is also a substring of another skill id (e.g.
                    # "implement" is in both "skill.implement" and
                    # "skill.test_implementation"). Exact match resolves it without
                    # depending on set iteration order (PYTHONHASHSEED).
                    if prefer_if_set_present:
                        exact_id = f"skill.{prefer_if_set_present}"
                        if exact_id in skills_pair:
                            preferred_skill_id = exact_id

                    # Fallback: deterministic ordered substring scan over a sorted
                    # list (never iterate a bare set — order is hash-seed-dependent).
                    if not preferred_skill_id and prefer_if_set_present:
                        for sid in sorted(skills_pair):
                            if sid.startswith("skill.") and prefer_if_set_present in sid:
                                preferred_skill_id = sid
                                break

                    if not preferred_skill_id:
                        mapping = {
                            "test_design": "skill.test_design",
                            "test_implementation": "skill.test_implementation",
                            "migration": "skill.migration",
                            "incident": "skill.incident",
                            "plan": "skill.plan",
                            "explore": "skill.explore",
                            "report": "skill.report",
                            "playwright_debug": "skill.debug",
                        }
                        preferred_skill_id = mapping.get(prefer_if_set_present)

                    if preferred_skill_id:
                        for item in scored_matches:
                            if item["skill_id"] == preferred_skill_id:
                                best = item
                                tie_break_applied = True
                                break

        if tie_break_applied:
            # After reassigning `best` to the preferred (possibly lower-scoring)
            # skill, recompute the runner-up as the highest-scoring skill that is
            # NOT the new best. Confidence must be derived from the ORIGINAL
            # race gap (`score_gap`, the real distance between the two top skills),
            # not from (new_best - runner_up) which can go negative and force
            # confidence to a constant "low".
            second = None
            second_score = -999
            for item in sorted_matches:
                if item["skill_id"] != best["skill_id"] and item["total_score"] > second_score:
                    second = item
                    second_score = item["total_score"]

    policy = config.get("confidence_policy", {})
    confidence_caps = []
    if tie_break_applied:
        base_confidence = "low" if original_score_gap <= policy.get("ordinary_gap_low_max", 2) else "medium"
        tie_break_max = policy.get("tie_break_max", "medium")
        final_confidence = min(
            (base_confidence, tie_break_max),
            key=lambda value: CONFIDENCE_RANK.get(value, 0),
        )
        confidence_caps.append("tie_break")
        margin = original_score_gap
    elif not second:
        base_confidence = policy.get("single_candidate_max", "medium")
        final_confidence = base_confidence
        confidence_caps.append("single_candidate")
        margin = None
    else:
        margin = best["total_score"] - second["total_score"]
        if margin <= policy.get("ordinary_gap_low_max", 2):
            base_confidence = "low"
        elif margin <= policy.get("ordinary_gap_medium_max", 5):
            base_confidence = "medium"
        else:
            base_confidence = "high"
        final_confidence = base_confidence

    if best["trigger_score"] == 0:
        keyword_only_max = policy.get("keyword_only_max", "low")
        final_confidence = min(
            (final_confidence, keyword_only_max),
            key=lambda value: CONFIDENCE_RANK.get(value, 0),
        )
        confidence_caps.append("keyword_only")

    chosen = best["skill"]
    variant_resolution = _resolve_skill_variant(chosen, intent_bias)
    composition = variant_resolution["composition"]

    return {
        "matched": True,
        "input": user_input,
        "strategy": "skill-trigger-v6",
        "confidence": final_confidence,
        "confidence_diagnostics": _confidence_diagnostics(
            policy,
            base_confidence=base_confidence,
            final_confidence=final_confidence,
            selection_mode="tie_break" if tie_break_applied else "ordinary",
            candidate_count=len(sorted_matches),
            runner_up_score=second.get("total_score") if second else None,
            margin=margin,
            matched_trigger_count=len(best["matched_triggers"]),
            keyword_evidence_count=len(best["evidence"]),
            caps=confidence_caps,
        ),
        "score": best["total_score"],
        "score_breakdown": {
            "trigger_score": best["trigger_score"],
            "keyword_bonus": best["keyword_bonus"],
        },
        "skill": {
            "id": chosen.get("id"),
            "name": chosen.get("name"),
            "context_mode": chosen.get("context"),
        },
        "behavior": composition["behavior"],
        "workflow": composition["workflow"],
        "domains": composition["domains"],
        "template": composition["template"],
        "checklists": composition["checklists"],
        "variant": variant_resolution["variant"],
        "variant_evidence": variant_resolution["evidence"],
        "variant_warnings": variant_resolution["warnings"],
        "matched_triggers": best["matched_triggers"],
        "evidence": best["evidence"],
        "candidates": [
            {
                "skill_id": item["skill_id"],
                "score": item["total_score"],
                "trigger_score": item["trigger_score"],
                "keyword_bonus": item["keyword_bonus"],
                "matched_triggers": item["matched_triggers"],
            }
            for item in sorted_matches[:5]
        ],
    }


def get_pack_routing_rule(pack: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    routing = pack.get("routing")
    if isinstance(routing, dict):
        return routing
    return None


def score_pack_match(user_input: str, pack: Dict[str, Any]) -> Dict[str, Any]:
    pack_id = pack.get("id")
    rule = get_pack_routing_rule(pack)

    if not rule:
        return {
            "matched": False,
            "pack_id": pack_id,
            "score": 0,
            "evidence": [],
            "reason": "No routing rule configured for pack",
        }

    any_hits = contains_any(user_input, rule.get("keywords_any", []))
    keyword_groups = rule.get("keywords_all_groups", [])
    all_groups_ok, all_group_hits = match_all_keyword_groups(user_input, keyword_groups)

    # A configured group set expresses required contextual evidence. Without every
    # group, generic terms such as "review", "refactor", or "playwright" must
    # not activate a technology-specific pack.
    if keyword_groups and not all_groups_ok:
        return {
            "matched": False,
            "pack_id": pack_id,
            "score": 0,
            "evidence": [],
            "reason": "Required pack keyword groups did not all match",
        }

    score = 0
    evidence = []

    if any_hits:
        score += min(len(any_hits), 3) * 2
        evidence.extend([{"type": "pack_keyword_any", "value": x} for x in any_hits])

    if all_group_hits:
        score += rule.get("score_bonus", 10)
        evidence.extend([{"type": "pack_keyword_group", "value": x} for x in all_group_hits])

    matched = score > 0

    return {
        "matched": matched,
        "pack_id": pack_id,
        "preferred_skill": rule.get("preferred_skill"),
        "score": score,
        "evidence": evidence,
        "pack": pack,
        "rule_source": "pack.routing" if isinstance(pack.get("routing"), dict) else "builtin-fallback",
    }


def route_pack(root: Path, user_input: str, chosen_skill_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    packs = load_pack_objects(root)
    candidates = []

    for pack in packs:
        scored = score_pack_match(user_input, pack)
        if not scored["matched"]:
            continue

        preferred_skill = scored.get("preferred_skill")
        pack_id = scored.get("pack_id")

        if preferred_skill and chosen_skill_id and preferred_skill != chosen_skill_id:
            if pack_id not in PACK_CROSS_SKILL_ALLOWED:
                continue
            scored["score"] -= 3
            scored["evidence"].append({
                "type": "pack_skill_mismatch_penalty",
                "value": f"preferred={preferred_skill}, chosen={chosen_skill_id}",
            })

        candidates.append(scored)

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x["score"], x.get("pack_id") or ""))
    return candidates[0]


def merge_skill_and_pack_route(skill_route: Dict[str, Any], pack_route: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not skill_route.get("matched"):
        return skill_route

    if not pack_route:
        result = dict(skill_route)
        result["strategy"] = "skill-trigger-v6"
        result["pack"] = None
        return result

    pack = pack_route["pack"]

    result = dict(skill_route)
    result["strategy"] = "skill+pack-v6"
    result["pack"] = {
        "id": pack.get("id"),
        "name": pack.get("name"),
        "purpose": pack.get("purpose"),
    }

    result["pack_score"] = pack_route.get("score")
    result["pack_rule_source"] = pack_route.get("rule_source")
    result["pack_evidence"] = pack_route.get("evidence", [])

    # A pack provides context for a selected skill. The skill owns non-null
    # behavior/workflow/template choices; pack scalars are fallbacks only.
    pk_behavior = pack.get("behavior") or pack.get("primary_behavior")
    if result.get("behavior") is None and pk_behavior is not None:
        result["behavior"] = pk_behavior
    pk_workflow = pack.get("workflow")
    if result.get("workflow") is None and pk_workflow is not None:
        result["workflow"] = pk_workflow
    pk_template = pack.get("template")
    if result.get("template") is None and pk_template is not None:
        result["template"] = pk_template

    def merge_unique(*values: List[str]) -> List[str]:
        merged = []
        for value in values:
            for item in value or []:
                if item not in merged:
                    merged.append(item)
        return merged

    result["domains"] = merge_unique(result.get("domains", []), pack.get("domains", []))
    result["checklists"] = merge_unique(result.get("checklists", []), pack.get("checklists", []))

    result["evidence"] = (result.get("evidence", []) or []) + (pack_route.get("evidence", []) or [])

    diagnostics = result.get("confidence_diagnostics")
    if isinstance(diagnostics, dict):
        diagnostics["pack_promotion"] = "disabled_by_policy"
        diagnostics["pack_score"] = pack_route.get("score", 0)
    return result


def _build_prefer_fallback(root: Path, user_input: str, preferred: str) -> Optional[Dict[str, Any]]:
    """Build a route result from a preferred skill when normal routing fails."""
    skill_obj = find_skill_by_query(root, preferred)
    if not skill_obj:
        return None

    skill_id = skill_obj.get("id")
    skill_name = skill_obj.get("name", preferred)

    config = get_effective_skill_routing_config(root)
    intent_bias = get_keyword_hits_map(root, user_input)
    variant_resolution = _resolve_skill_variant(skill_obj, intent_bias)
    composition = variant_resolution["composition"]
    policy = config.get("confidence_policy", {})
    fallback_confidence = policy.get("fallback_confidence", "low")
    pack_route = route_pack(root, user_input, chosen_skill_id=skill_id)

    result = {
        "matched": True,
        "input": user_input,
        "strategy": "skill+pack-v6" if pack_route else "skill-trigger-v6",
        "confidence": fallback_confidence,
        "confidence_diagnostics": _confidence_diagnostics(
            policy,
            base_confidence=fallback_confidence,
            final_confidence=fallback_confidence,
            selection_mode="prefer_fallback",
            candidate_count=0,
            runner_up_score=None,
            margin=None,
            matched_trigger_count=0,
            keyword_evidence_count=0,
            caps=["fallback"],
        ),
        "score": 0,
        "score_breakdown": {"trigger_score": 0, "keyword_bonus": 0},
        "skill": {
            "id": skill_id,
            "name": skill_name,
            "context_mode": skill_obj.get("context", "inherit"),
        },
        "behavior": composition["behavior"],
        "workflow": composition["workflow"],
        "domains": composition["domains"],
        "template": composition["template"],
        "checklists": composition["checklists"],
        "variant": variant_resolution["variant"],
        "variant_evidence": variant_resolution["evidence"],
        "variant_warnings": variant_resolution["warnings"],
        "matched_triggers": [f"--prefer {preferred}"],
        "evidence": [{"type": "prefer_fallback", "value": preferred}],
        "candidates": [],
    }

    if pack_route:
        result = merge_skill_and_pack_route(result, pack_route)

    return result


def build_recommendation_from_route(route_result: Dict[str, Any]) -> Dict[str, Any]:
    if not route_result.get("matched"):
        return {
            "matched": False,
            "mode": "recommend",
            "input": route_result.get("input"),
            "confidence": route_result.get("confidence", "low"),
            "confidence_diagnostics": route_result.get("confidence_diagnostics"),
            "reason": route_result.get("reason", "No recommendation available"),
            "recommended": None,
        }

    skill_obj = route_result.get("skill") or {}
    pack_obj = route_result.get("pack") or {}

    return {
        "matched": True,
        "mode": "recommend",
        "input": route_result.get("input"),
        "confidence": route_result.get("confidence"),
        "recommended": {
            "skill": skill_obj.get("id"),
            "variant": route_result.get("variant"),
            "pack": pack_obj.get("id"),
            "behavior": route_result.get("behavior"),
            "workflow": route_result.get("workflow"),
            "template": route_result.get("template"),
            "domains": route_result.get("domains", []),
            "checklists": route_result.get("checklists", []),
        },
        "strategy": route_result.get("strategy"),
        "confidence_diagnostics": route_result.get("confidence_diagnostics"),
        "evidence": route_result.get("evidence", []),
        "pack_evidence": route_result.get("pack_evidence", []),
    }


def compose_selection(
    root: Path,
    skill_query: Optional[str] = None,
    pack_query: Optional[str] = None,
    behavior: Optional[str] = None,
    workflow: Optional[str] = None,
    template: Optional[str] = None,
    domains: Optional[List[str]] = None,
    checklists: Optional[List[str]] = None,
) -> Dict[str, Any]:
    domains = domains or []
    checklists = checklists or []

    skill_obj = find_skill_by_query(root, skill_query) if skill_query else None
    pack_obj = None
    warnings: List[str] = []
    unresolved: Dict[str, str] = {}

    if skill_query and not skill_obj:
        warnings.append(f"Requested skill not found: {skill_query}")
        unresolved["skill"] = skill_query

    if pack_query:
        pack_candidate = find_pack_by_query(root, pack_query)
        if pack_candidate and pack_candidate.get("id"):
            pack_obj = find_pack_object_by_id(root, pack_candidate["id"]) or pack_candidate
        else:
            warnings.append(f"Requested pack not found: {pack_query}")
            unresolved["pack"] = pack_query

    result = {
        "matched": True,
        "mode": "compose",
        "skill": skill_obj.get("id") if skill_obj else None,
        "pack": pack_obj.get("id") if pack_obj else None,
        "behavior": None,
        "workflow": None,
        "template": None,
        "domains": [],
        "checklists": [],
        "sources": {},
        "warnings": warnings,
        "unresolved": unresolved,
    }

    if skill_obj:
        if skill_obj.get("behavior"):
            result["behavior"] = skill_obj.get("behavior")
            result["sources"]["behavior"] = "skill"
        if skill_obj.get("workflow"):
            result["workflow"] = skill_obj.get("workflow")
            result["sources"]["workflow"] = "skill"
        if skill_obj.get("template"):
            result["template"] = skill_obj.get("template")
            result["sources"]["template"] = "skill"
        if skill_obj.get("domains"):
            result["domains"] = list(skill_obj.get("domains", []))
            result["sources"]["domains"] = "skill"
        if skill_obj.get("checklists"):
            result["checklists"] = list(skill_obj.get("checklists", []))
            result["sources"]["checklists"] = "skill"

    if pack_obj:
        if pack_obj.get("behavior") or pack_obj.get("primary_behavior"):
            result["behavior"] = pack_obj.get("behavior") or pack_obj.get("primary_behavior")
            result["sources"]["behavior"] = "pack"
        if pack_obj.get("workflow"):
            result["workflow"] = pack_obj.get("workflow")
            result["sources"]["workflow"] = "pack"
        if pack_obj.get("template"):
            result["template"] = pack_obj.get("template")
            result["sources"]["template"] = "pack"
        if pack_obj.get("domains"):
            result["domains"] = list(pack_obj.get("domains", []))
            result["sources"]["domains"] = "pack"
        if pack_obj.get("checklists"):
            result["checklists"] = list(pack_obj.get("checklists", []))
            result["sources"]["checklists"] = "pack"

    if behavior:
        result["behavior"] = behavior
        result["sources"]["behavior"] = "cli"

    if workflow:
        result["workflow"] = workflow
        result["sources"]["workflow"] = "cli"

    if template:
        result["template"] = template
        result["sources"]["template"] = "cli"

    if domains:
        merged_domains = list(dict.fromkeys((result["domains"] or []) + domains))
        result["domains"] = merged_domains
        prev = result["sources"].get("domains")
        result["sources"]["domains"] = f"{prev}+cli" if prev else "cli"

    if checklists:
        merged_checklists = list(dict.fromkeys((result["checklists"] or []) + checklists))
        result["checklists"] = merged_checklists
        prev = result["sources"].get("checklists")
        result["sources"]["checklists"] = f"{prev}+cli" if prev else "cli"

    return result


def render_route_text(route_result: Dict[str, Any]):
    if not route_result.get("matched"):
        click.echo("Route: NO MATCH")
        click.echo(f"Input: {route_result.get('input')}")
        click.echo(f"Reason: {route_result.get('reason')}")
        click.echo(f"Confidence: {route_result.get('confidence')}")
        return

    click.echo("Route: MATCHED")
    click.echo(f"Input: {route_result.get('input')}")
    click.echo(f"Strategy: {route_result.get('strategy')}")
    click.echo(f"Confidence: {route_result.get('confidence')}")
    click.echo(f"Score: {route_result.get('score')}")

    breakdown = route_result.get("score_breakdown", {})
    if breakdown:
        click.echo(
            f"Score breakdown: trigger={breakdown.get('trigger_score', 0)}, "
            f"keyword_bonus={breakdown.get('keyword_bonus', 0)}"
        )

    skill = route_result.get("skill") or {}
    click.echo(f"Skill: {skill.get('id')} ({skill.get('name')})")
    click.echo(f"Variant: {route_result.get('variant') or '-'}")
    click.echo(f"Context mode: {skill.get('context_mode')}")

    pack = route_result.get("pack")
    if pack:
        click.echo(f"Pack: {pack.get('id')} ({pack.get('name')})")
        click.echo(f"Pack purpose: {pack.get('purpose')}")
        click.echo(f"Pack score: {route_result.get('pack_score')}")
        click.echo(f"Pack rule source: {route_result.get('pack_rule_source')}")

    click.echo(f"Behavior: {route_result.get('behavior')}")
    click.echo(f"Workflow: {route_result.get('workflow')}")
    click.echo(f"Template: {route_result.get('template')}")

    domains = route_result.get("domains", [])
    checklists = route_result.get("checklists", [])
    matched_triggers = route_result.get("matched_triggers", [])
    evidence = route_result.get("evidence", [])
    pack_evidence = route_result.get("pack_evidence", [])
    candidates = route_result.get("candidates", [])

    click.echo(f"Matched triggers: {', '.join(matched_triggers) if matched_triggers else '-'}")
    click.echo(f"Domains: {', '.join(domains) if domains else '-'}")
    click.echo(f"Checklists: {', '.join(checklists) if checklists else '-'}")

    if evidence:
        click.echo("Evidence:")
        for e in evidence:
            click.echo(f"  - {e.get('type')}: {e.get('value')}")

    if pack_evidence:
        click.echo("Pack evidence:")
        for e in pack_evidence:
            click.echo(f"  - {e.get('type')}: {e.get('value')}")

    if candidates:
        click.echo("Top candidates:")
        for c in candidates:
            click.echo(
                f"  - {c.get('skill_id')}: score={c.get('score')}, "
                f"trigger={c.get('trigger_score')}, bonus={c.get('keyword_bonus')}, "
                f"matched={c.get('matched_triggers')}"
            )
