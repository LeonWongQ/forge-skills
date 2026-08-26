# -*- coding: utf-8 -*-
"""Deterministic cross-registry semantic validation for Forge."""

from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .output_validation import resolve_template_output_schema
from .registry_discovery import load_array_registry, load_modules_registry, load_pack_objects, load_skill_routing_config


ENGINE_ORDER = [
    "engine.discover",
    "engine.evidence",
    "engine.context",
    "engine.reasoning",
    "engine.planning",
    "engine.execution",
    "engine.verification",
    "engine.delivery",
]
DEDICATED_LAYERS = {
    "skills": ("skills.json", "skills"),
    "behaviors": ("behaviors.json", "behaviors"),
    "domains": ("domains.json", "domains"),
    "templates": ("templates.json", "templates"),
    "checklists": ("checklists.json", "checklists"),
    "reports": ("reports.json", "reports"),
}


def _issue(code: str, message: str, **details: Any) -> Dict[str, Any]:
    issue = {"code": code, "message": message}
    if details:
        issue["details"] = details
    return issue


def _duplicate_issues(items: Iterable[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    ids = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
    return [
        _issue("SEMANTIC_DUPLICATE_ID", f"Duplicate id in {source}: {item_id}", source=source, id=item_id)
        for item_id, count in sorted(Counter(ids).items())
        if count > 1
    ]


def _known_by_layer(modules: Dict[str, Any]) -> Dict[str, set[str]]:
    layers = modules.get("layers", {}) if isinstance(modules, dict) else {}
    return {
        layer: {
            item.get("id") for item in items
            if isinstance(item, dict) and item.get("id")
        }
        for layer, items in layers.items()
        if isinstance(items, list)
    }


def _validate_keyword_set_reference(
    issues: List[Dict[str, Any]],
    keyword_sets: Dict[str, Any],
    value: Any,
    *,
    source: str,
    field: str,
    skill: Optional[str] = None,
    rule_type: Optional[str] = None,
    rule_index: Optional[int] = None,
) -> None:
    if not value or value in keyword_sets:
        return
    details = {"source": source, "field": field, "keyword_set": value}
    if skill is not None:
        details["skill"] = skill
    if rule_type is not None:
        details["rule_type"] = rule_type
    if rule_index is not None:
        details["rule_index"] = rule_index
    issues.append(_issue(
        "SEMANTIC_ROUTING_KEYWORD_SET_UNKNOWN",
        f"{source} references unknown keyword set: {value}",
        **details,
    ))


def validate_semantics(root: Path) -> List[Dict[str, Any]]:
    """Return sorted, finite semantic issues without interpreting prose content."""
    issues: List[Dict[str, Any]] = []
    modules = load_modules_registry(root)
    layers = modules.get("layers", {}) if isinstance(modules, dict) else {}
    known_layers = _known_by_layer(modules)
    known_ids = set().union(*known_layers.values()) if known_layers else set()

    for layer, items in sorted(layers.items() if isinstance(layers, dict) else []):
        if isinstance(items, list):
            issues.extend(_duplicate_issues(items, f"modules.json.layers.{layer}"))

    for layer, (filename, key) in DEDICATED_LAYERS.items():
        entries = load_array_registry(root, filename, [key])
        issues.extend(_duplicate_issues(entries, filename))
        module_entries = {
            item.get("id"): item for item in layers.get(layer, [])
            if isinstance(item, dict) and item.get("id")
        }
        dedicated_entries = {item.get("id"): item for item in entries if item.get("id")}
        for item_id in sorted(set(module_entries) ^ set(dedicated_entries)):
            issues.append(_issue(
                "SEMANTIC_MODULE_REGISTRY_ORPHAN",
                f"{item_id} is not represented consistently between modules.json and {filename}",
                layer=layer,
                id=item_id,
            ))
        for item_id in sorted(set(module_entries) & set(dedicated_entries)):
            module_path = module_entries[item_id].get("path")
            dedicated_path = dedicated_entries[item_id].get("path")
            if module_path and dedicated_path and module_path != dedicated_path:
                issues.append(_issue(
                    "SEMANTIC_MODULE_PATH_MISMATCH",
                    f"{item_id} has different paths in modules.json and {filename}",
                    id=item_id,
                    module_path=module_path,
                    registry_path=dedicated_path,
                ))

    domains = load_array_registry(root, "domains.json", ["domains"])
    domain_ids = {domain.get("id") for domain in domains if domain.get("id")}
    seen_aliases = {}
    for domain in domains:
        domain_id = domain.get("id", "<unknown>")
        for related in domain.get("related_domains", []):
            if related not in domain_ids:
                issues.append(_issue("SEMANTIC_DOMAIN_RELATED_UNKNOWN", f"{domain_id} references unknown related domain: {related}", domain=domain_id, related_domain=related))
        activation = domain.get("activation_signals", {})
        if activation is not None and not isinstance(activation, dict):
            issues.append(_issue("SEMANTIC_DOMAIN_SIGNALS_INVALID", f"{domain_id} activation_signals must be an object", domain=domain_id))
        for alias in domain.get("aliases", []):
            if not isinstance(alias, str) or not alias.strip():
                issues.append(_issue("SEMANTIC_DOMAIN_ALIAS_INVALID", f"{domain_id} has an invalid alias", domain=domain_id))
                continue
            normalized = " ".join(alias.lower().split())
            previous = seen_aliases.get(normalized)
            if previous and previous != domain_id:
                issues.append(_issue("SEMANTIC_DOMAIN_ALIAS_AMBIGUOUS", f"Alias {alias!r} is shared by {previous} and {domain_id}", alias=alias, first_domain=previous, second_domain=domain_id))
            seen_aliases[normalized] = domain_id

    templates = load_array_registry(root, "templates.json", ["templates"])
    bindings = load_array_registry(root, "template-outputs.json", ["template_outputs"])
    issues.extend(_duplicate_issues(bindings, "template-outputs.json"))
    template_ids = {item.get("id") for item in templates if item.get("id")}
    binding_ids = {item.get("template_id") for item in bindings if item.get("template_id")}
    for template_id in sorted(template_ids ^ binding_ids):
        issues.append(_issue(
            "SEMANTIC_TEMPLATE_OUTPUT_COVERAGE",
            f"Template output binding missing or orphaned for: {template_id}",
            template_id=template_id,
        ))
    for template_id in sorted(template_ids & binding_ids):
        _, errors = resolve_template_output_schema(root, template_id)
        for error in errors:
            issues.append(_issue(error["code"], error["message"], template_id=template_id, **error.get("details", {})))

    workflows = load_array_registry(root, "workflows.json", ["workflows"])
    issues.extend(_duplicate_issues(workflows, "workflows.json"))
    workflow_ids = {workflow.get("id") for workflow in workflows if workflow.get("id")}
    default_workflow = (root / "registry" / "workflows.json")
    workflow_data = {}
    if default_workflow.exists():
        from .helpers import load_json
        workflow_data = load_json(default_workflow)
    if workflow_data.get("default_workflow") not in workflow_ids:
        issues.append(_issue("SEMANTIC_DEFAULT_WORKFLOW_UNKNOWN", "default_workflow does not resolve", workflow=workflow_data.get("default_workflow")))
    engine_ids = known_layers.get("engine", set())
    order = {stage: index for index, stage in enumerate(ENGINE_ORDER)}
    for workflow in workflows:
        workflow_id = workflow.get("id", "<unknown>")
        stages = workflow.get("stages")
        if not isinstance(stages, list):
            issues.append(_issue("SEMANTIC_WORKFLOW_STAGES_INVALID", f"{workflow_id} has no valid stages list", workflow=workflow_id))
            continue
        if len(stages) != len(set(stages)):
            issues.append(_issue("SEMANTIC_WORKFLOW_STAGE_DUPLICATE", f"{workflow_id} contains duplicate stages", workflow=workflow_id))
        unknown = sorted(set(stages) - engine_ids)
        for stage in unknown:
            issues.append(_issue("SEMANTIC_WORKFLOW_STAGE_UNKNOWN", f"{workflow_id} references unknown engine stage: {stage}", workflow=workflow_id, stage=stage))
        if stages and stages[0] != "engine.discover":
            issues.append(_issue("SEMANTIC_WORKFLOW_START_INVALID", f"{workflow_id} must start with engine.discover", workflow=workflow_id))
        if stages.count("engine.delivery") != 1 or (stages and stages[-1] != "engine.delivery"):
            issues.append(_issue("SEMANTIC_WORKFLOW_DELIVERY_INVALID", f"{workflow_id} must end with one engine.delivery", workflow=workflow_id))
        ranked = [order[stage] for stage in stages if stage in order]
        if ranked != sorted(ranked):
            issues.append(_issue("SEMANTIC_WORKFLOW_ORDER_INVALID", f"{workflow_id} stages must follow canonical engine order", workflow=workflow_id))

    compositions = load_array_registry(root, "compositions.json", ["compositions"])
    for composition in compositions:
        for behavior in composition.get("secondary_behaviors", []):
            if behavior not in known_layers.get("behaviors", set()):
                issues.append(_issue("SEMANTIC_SECONDARY_BEHAVIOR_UNKNOWN", f"{composition.get('id')} references unknown secondary behavior: {behavior}", composition=composition.get("id"), behavior=behavior))

    skills = load_array_registry(root, "skills.json", ["skills"])
    skill_ids = {skill.get("id") for skill in skills if skill.get("id")}
    routing = load_skill_routing_config(root)
    keyword_sets = routing.get("keyword_sets", {}) if isinstance(routing, dict) else {}
    generic_penalties = routing.get("generic_trigger_penalties", {}) if isinstance(routing, dict) else {}
    bias_rules = routing.get("skill_bias_rules", {}) if isinstance(routing, dict) else {}

    for mapping_name, mapping in (("generic_trigger_penalties", generic_penalties), ("skill_bias_rules", bias_rules)):
        if isinstance(mapping, dict):
            for skill_id in sorted(mapping):
                if skill_id not in skill_ids:
                    issues.append(_issue(
                        "SEMANTIC_ROUTING_SKILL_UNKNOWN",
                        f"{mapping_name} references unknown skill: {skill_id}",
                        mapping=mapping_name,
                        skill=skill_id,
                    ))

    if isinstance(bias_rules, dict):
        for skill_id, rule in sorted(bias_rules.items()):
            if not isinstance(rule, dict):
                continue
            for rule_type in ("keyword_bonus", "keyword_penalty", "keyword_penalty_when_trigger_matched"):
                for index, item in enumerate(rule.get(rule_type, [])):
                    if isinstance(item, dict):
                        _validate_keyword_set_reference(
                            issues, keyword_sets, item.get("keyword_set"),
                            source="skill_bias_rules", field="keyword_set", skill=skill_id,
                            rule_type=rule_type, rule_index=index,
                        )
            for index, item in enumerate(rule.get("keyword_penalty_when_absent", [])):
                if isinstance(item, dict):
                    for field in ("required_set", "keyword_set"):
                        _validate_keyword_set_reference(
                            issues, keyword_sets, item.get(field),
                            source="skill_bias_rules", field=field, skill=skill_id,
                            rule_type="keyword_penalty_when_absent", rule_index=index,
                        )
            postmortem = rule.get("postmortem_hint_bonus")
            if isinstance(postmortem, dict):
                _validate_keyword_set_reference(
                    issues, keyword_sets, postmortem.get("requires_keyword_set"),
                    source="skill_bias_rules", field="requires_keyword_set", skill=skill_id,
                    rule_type="postmortem_hint_bonus",
                )

    for index, rule in enumerate(routing.get("tie_break_rules", []) if isinstance(routing, dict) else []):
        pair = rule.get("skills", []) if isinstance(rule, dict) else []
        if len(pair) != 2 or len(set(pair)) != 2 or any(skill not in skill_ids for skill in pair):
            issues.append(_issue("SEMANTIC_TIE_BREAK_INVALID", f"Invalid tie-break skill pair: {pair}", skills=pair))
        for key in ("prefer_if_set_present", "avoid_if_set_present"):
            _validate_keyword_set_reference(
                issues, keyword_sets, rule.get(key) if isinstance(rule, dict) else None,
                source="tie_break_rules", field=key, rule_type="tie_break", rule_index=index,
            )

    confidence_policy = routing.get("confidence_policy", {}) if isinstance(routing, dict) else {}
    if isinstance(confidence_policy, dict):
        low_max = confidence_policy.get("ordinary_gap_low_max")
        medium_max = confidence_policy.get("ordinary_gap_medium_max")
        if isinstance(low_max, int) and isinstance(medium_max, int) and low_max > medium_max:
            issues.append(_issue(
                "SEMANTIC_CONFIDENCE_POLICY_GAP_ORDER_INVALID",
                "confidence_policy ordinary_gap_low_max must not exceed ordinary_gap_medium_max",
                ordinary_gap_low_max=low_max,
                ordinary_gap_medium_max=medium_max,
            ))

    ask_policy = routing.get("ask_policy", {}) if isinstance(routing, dict) else {}
    if isinstance(ask_policy, dict):
        expected_order = ["runtime", "explicit_skill", "native_first", "forge_first", "native_fallback"]
        if ask_policy.get("ownership_order") != expected_order:
            issues.append(_issue(
                "SEMANTIC_ASK_POLICY_ORDER_INVALID",
                "ask_policy ownership_order must use the canonical ownership precedence",
                ownership_order=ask_policy.get("ownership_order"),
            ))
        forge_first_skills = ask_policy.get("forge_first_skills", [])
        for skill_id in forge_first_skills if isinstance(forge_first_skills, list) else []:
            if skill_id not in skill_ids:
                issues.append(_issue(
                    "SEMANTIC_ASK_POLICY_FORGE_SKILL_UNKNOWN",
                    f"ask_policy references unknown Forge-first skill: {skill_id}",
                    skill=skill_id,
                ))
        native_entries = ask_policy.get("native_first", [])
        if isinstance(native_entries, list):
            native_ids = [entry.get("id") for entry in native_entries if isinstance(entry, dict)]
            native_skills = [entry.get("skill") for entry in native_entries if isinstance(entry, dict)]
            for value, label in ((native_ids, "id"), (native_skills, "skill")):
                for duplicate in sorted(item for item, count in Counter(value).items() if item and count > 1):
                    issues.append(_issue(
                        "SEMANTIC_ASK_POLICY_NATIVE_DUPLICATE",
                        f"ask_policy native_first has duplicate {label}: {duplicate}",
                        field=label,
                        value=duplicate,
                    ))

    contracts = load_array_registry(root, "contracts.json", ["contracts"])
    issues.extend(_duplicate_issues(contracts, "contracts.json"))
    for contract in contracts:
        contract_id = contract.get("id", "<unknown>")
        baseline_path = contract.get("baseline_schema")
        current_path = contract.get("current_schema")
        if baseline_path and baseline_path == current_path:
            issues.append(_issue("SEMANTIC_CONTRACT_SCHEMA_BASELINE_EQUAL", f"{contract_id} baseline_schema and current_schema must differ", contract=contract_id))
        compatibility = contract.get("compatibility", {})
        fixtures = contract.get("fixtures", {})
        if isinstance(compatibility, dict) and isinstance(fixtures, dict):
            for direction, group in (("baseline_to_current", "baseline_valid"), ("current_to_baseline", "current_valid")):
                if compatibility.get(direction) == "required" and not fixtures.get(group):
                    issues.append(_issue("SEMANTIC_CONTRACT_REQUIRED_FIXTURES_EMPTY", f"{contract_id} requires non-empty {group} fixtures", contract=contract_id, group=group))
            groups = [fixtures.get("baseline_valid", []), fixtures.get("current_valid", []), fixtures.get("invalid", [])]
            flattened = [path for group in groups if isinstance(group, list) for path in group]
            if len(flattened) != len(set(flattened)):
                issues.append(_issue("SEMANTIC_CONTRACT_FIXTURE_GROUP_OVERLAP", f"{contract_id} fixture paths must not overlap across expectation groups", contract=contract_id))

    reference_layers = {
        "kernel": "kernel", "runtime": "runtime", "behaviors": "behaviors", "domains": "domains", "engine": "engine",
    }
    for pack in load_pack_objects(root):
        pack_id = pack.get("id", "<unknown>")
        pack_modules = pack.get("modules", {})
        if not isinstance(pack_modules, dict):
            continue
        for field, layer in reference_layers.items():
            for module_id in pack_modules.get(field, []):
                if module_id not in known_layers.get(layer, set()):
                    issues.append(_issue("SEMANTIC_PACK_MODULE_UNKNOWN", f"{pack_id} references unknown {field} module: {module_id}", pack=pack_id, module_type=field, module=module_id))
        for field, allowed in (("workflow", workflow_ids), ("template", known_layers.get("templates", set())), ("checklists", known_layers.get("checklists", set())), ("reports", known_layers.get("reports", set()))):
            values = pack.get(field, []) if field in ("checklists", "reports") else [pack.get(field)]
            for value in values:
                if value and value not in allowed:
                    issues.append(_issue("SEMANTIC_PACK_REFERENCE_UNKNOWN", f"{pack_id} references unknown {field}: {value}", pack=pack_id, field=field, reference=value))

    return sorted(issues, key=lambda item: (item["code"], item["message"]))
