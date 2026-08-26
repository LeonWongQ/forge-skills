# -*- coding: utf-8 -*-
"""Forge CLI — validation checks: registry, paths, refs, packs, pack-refs."""

from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List

from .constants import (
    CHECK_CONTRACTS,
    CHECK_DERIVED_REGISTRY,
    CHECK_PACK_REFS,
    CHECK_PACKS,
    CHECK_PATHS,
    CHECK_REFS,
    CHECK_REGISTRY,
    CHECK_SEMANTICS,
    REGISTRY_SCHEMA_CANDIDATES,
    REGISTRY_WITHOUT_SCHEMA,
    NON_REGISTRY_SCHEMAS,
)
from .helpers import debug, load_json_file_safe, now_ms, resolve_registered_path
from .registry_discovery import (
    collect_known_ids_from_modules_registry,
    find_schema_file,
    get_registry_json_files,
    get_schema_files,
    load_array_registry,
    load_modules_registry,
    load_pack_index,
    load_pack_objects,
    load_skill_routing_config,
    packs_dir,
    registry_dir,
    validate_instance_with_schema,
)
from .result_builders import add_msg, finalize_check_result, make_check_result


def _load_jsonschema():
    """Import jsonschema only for checks that validate JSON schemas."""
    if find_spec("jsonschema") is None:
        return None
    import jsonschema

    return jsonschema


# ============================================================
# Check: Registry Schema Validation
# ============================================================

def check_registry(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_REGISTRY, passed=True)
    jsonschema = _load_jsonschema()

    rd = registry_dir(root)
    if not rd.exists():
        result["passed"] = False
        add_msg(result, "error", "REGISTRY_DIR_MISSING", f"Registry directory not found: {rd}")
        return finalize_check_result(result, start)

    registry_files = get_registry_json_files(root)
    if not registry_files:
        result["passed"] = False
        add_msg(result, "error", "REGISTRY_FILES_MISSING", "No registry JSON files found")
        return finalize_check_result(result, start)

    schema_files = get_schema_files(root)
    if not schema_files:
        add_msg(result, "warning", "SCHEMA_FILES_NOT_FOUND", "No schema JSON files found under registry/schemas")

    parsed_schemas: Dict[str, Dict[str, Any]] = {}

    for sf in schema_files:
        schema_data, err = load_json_file_safe(sf)
        if err:
            result["passed"] = False
            add_msg(result, "error", "INVALID_SCHEMA_JSON", f"Invalid schema JSON: {sf.name}", err)
            continue

        if jsonschema is not None:
            try:
                validator_cls = jsonschema.validators.validator_for(schema_data)
                validator_cls.check_schema(schema_data)
            except Exception as e:
                result["passed"] = False
                add_msg(result, "error", "INVALID_JSON_SCHEMA", f"Invalid JSON Schema: {sf.name}", str(e))
                continue

        parsed_schemas[sf.name] = schema_data
        debug(ctx, f"Loaded schema JSON: {sf}")

    if jsonschema is None:
        add_msg(result, "warning", "JSONSCHEMA_NOT_INSTALLED", "jsonschema not installed; schema validation skipped")

    parsed_registry: Dict[str, Any] = {}

    for jf in registry_files:
        data, err = load_json_file_safe(jf)
        if err:
            result["passed"] = False
            add_msg(result, "error", "INVALID_JSON", f"Invalid JSON: {jf.name}", err)
            continue

        parsed_registry[jf.name] = data
        debug(ctx, f"Loaded registry JSON: {jf}")

    if jsonschema is None:
        return finalize_check_result(result, start)

    for registry_name, instance in parsed_registry.items():
        if registry_name in REGISTRY_SCHEMA_CANDIDATES:
            candidates = REGISTRY_SCHEMA_CANDIDATES[registry_name]
            schema_file = find_schema_file(root, registry_name.replace(".json", ""), candidates)

            if not schema_file:
                result["passed"] = False
                add_msg(result, "error", "SCHEMA_NOT_FOUND", f"Expected schema file not found for registry: {registry_name}")
                continue

            schema_data = parsed_schemas.get(schema_file.name)
            if not schema_data:
                result["passed"] = False
                add_msg(result, "error", "SCHEMA_NOT_LOADED", f"Schema file could not be loaded for registry: {registry_name}")
                continue

            errors = validate_instance_with_schema(instance, schema_data)
            real_errors = [e for e in errors if e["code"] != "JSONSCHEMA_NOT_INSTALLED"]

            if real_errors:
                result["passed"] = False
                for e in real_errors:
                    add_msg(
                        result,
                        "error",
                        e["code"],
                        f"{registry_name} does not match {schema_file.name}: {e['message']}",
                        {
                            "instance_path": e["path"],
                            "schema_path": e["schema_path"],
                        }
                    )
            else:
                add_msg(result, "info", "SCHEMA_VALID", f"{registry_name} matches {schema_file.name}")

        elif registry_name in REGISTRY_WITHOUT_SCHEMA:
            add_msg(result, "info", "NO_SCHEMA_EXPECTED", f"{registry_name} has no schema by design")

        else:
            add_msg(result, "warning", "UNCLASSIFIED_REGISTRY_FILE", f"Registry file is not classified in CLI rules: {registry_name}")

    mapped_schema_names = set()
    for candidates in REGISTRY_SCHEMA_CANDIDATES.values():
        for c in candidates:
            mapped_schema_names.add(c)

    for sf in parsed_schemas.keys():
        if sf in NON_REGISTRY_SCHEMAS:
            add_msg(result, "info", "NON_REGISTRY_SCHEMA", f"{sf} is a non-registry schema and was syntax-checked only")
        elif sf not in mapped_schema_names:
            add_msg(result, "info", "UNMAPPED_SCHEMA", f"{sf} is not currently mapped to a registry file")

    return finalize_check_result(result, start)


# ============================================================
# Check: Module Paths
# ============================================================

def check_paths(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_PATHS, passed=True)

    modules = load_modules_registry(root)
    if not modules:
        result["passed"] = False
        add_msg(result, "error", "MODULES_REGISTRY_MISSING", "modules registry not found")
        return finalize_check_result(result, start)

    layers = modules.get("layers", {})
    if not isinstance(layers, dict):
        result["passed"] = False
        add_msg(result, "error", "INVALID_MODULES_REGISTRY", "modules registry missing valid 'layers' object")
        return finalize_check_result(result, start)

    for layer_name, items in layers.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            rel = item.get("path")
            item_id = item.get("id", "<unknown>")
            if rel:
                full, path_error = resolve_registered_path(root, rel)
                if path_error:
                    result["passed"] = False
                    add_msg(
                        result,
                        "error",
                        path_error["code"],
                        f"Registered path is invalid for {item_id}: {rel}",
                        {"layer": layer_name, "item_id": item_id, **path_error},
                    )
                elif not full.exists():
                    result["passed"] = False
                    add_msg(result, "error", "PATH_MISSING", f"Missing path for {item_id}: {rel}")
                else:
                    debug(ctx, f"[{layer_name}] exists: {rel}")

    if result["passed"]:
        add_msg(result, "info", "PATH_CHECK_OK", "All registered module paths exist")

    return finalize_check_result(result, start)


# ============================================================
# Check: Cross-References
# ============================================================

def check_refs(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_REFS, passed=True)

    known_ids = collect_known_ids_from_modules_registry(root)
    if not known_ids:
        result["passed"] = False
        add_msg(result, "error", "KNOWN_IDS_EMPTY", "Unable to build known id set from registries")
        return finalize_check_result(result, start)

    skills = load_array_registry(root, "skills.json", ["skills"])
    workflows = load_array_registry(root, "workflows.json", ["workflows"])
    compositions = load_array_registry(root, "compositions.json", ["compositions"])
    packs = load_array_registry(root, "packs.json", ["packs"])

    known_workflow_ids = {w.get("id") for w in workflows if isinstance(w, dict) and w.get("id")}
    known_pack_ids = {p.get("id") for p in packs if isinstance(p, dict) and p.get("id")}

    routing_config = load_skill_routing_config(root)
    keyword_sets = routing_config.get("keyword_sets", {}) if isinstance(routing_config, dict) else {}

    for skill in skills:
        sid = skill.get("id", "<unknown-skill>")
        behavior = skill.get("behavior")
        if behavior and behavior not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_BEHAVIOR_REF", f"{sid} references unknown behavior: {behavior}")

        workflow = skill.get("workflow")
        if workflow and workflow not in known_workflow_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_WORKFLOW_REF", f"{sid} references unknown workflow: {workflow}")

        template = skill.get("template")
        if template and template not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_TEMPLATE_REF", f"{sid} references unknown template: {template}")

        for domain in skill.get("domains", []):
            if domain not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_DOMAIN_REF", f"{sid} references unknown domain: {domain}")

        for checklist in skill.get("checklists", []):
            if checklist not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_CHECKLIST_REF", f"{sid} references unknown checklist: {checklist}")

        variant_types = set()
        variant_selectors = {}
        for variant in skill.get("variants", []):
            vt = variant.get("type", "<unknown>")
            if vt in variant_types:
                result["passed"] = False
                add_msg(result, "error", "DUPLICATE_VARIANT_TYPE", f"{sid} defines duplicate variant type: {vt}")
            variant_types.add(vt)
            selection = variant.get("selection")
            if isinstance(selection, dict):
                priority = selection.get("priority")
                keyword_set_names = selection.get("keyword_sets_any", [])
                for keyword_set in keyword_set_names:
                    if keyword_set not in keyword_sets:
                        result["passed"] = False
                        add_msg(result, "error", "UNKNOWN_VARIANT_KEYWORD_SET", f"{sid} variant[{vt}] references unknown keyword set: {keyword_set}")
                    selector_key = (priority, keyword_set)
                    if selector_key in variant_selectors:
                        result["passed"] = False
                        add_msg(result, "error", "AMBIGUOUS_VARIANT_SELECTOR", f"{sid} variants {variant_selectors[selector_key]} and {vt} share priority and keyword set: {keyword_set}")
                    variant_selectors[selector_key] = vt
            vbehavior = variant.get("behavior")
            if vbehavior and vbehavior not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_VARIANT_BEHAVIOR_REF", f"{sid} variant[{vt}] references unknown behavior: {vbehavior}")
            vtemplate = variant.get("template")
            if vtemplate and vtemplate not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_VARIANT_TEMPLATE_REF", f"{sid} variant[{vt}] references unknown template: {vtemplate}")
            for vd in variant.get("domains", []):
                if vd not in known_ids:
                    result["passed"] = False
                    add_msg(result, "error", "UNKNOWN_VARIANT_DOMAIN_REF", f"{sid} variant[{vt}] references unknown domain: {vd}")
            for vc in variant.get("checklists", []):
                if vc not in known_ids:
                    result["passed"] = False
                    add_msg(result, "error", "UNKNOWN_VARIANT_CHECKLIST_REF", f"{sid} variant[{vt}] references unknown checklist: {vc}")

    for comp in compositions:
        cid = comp.get("id", "<unknown-composition>")
        behavior = comp.get("primary_behavior")
        if behavior and behavior not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_PRIMARY_BEHAVIOR_REF", f"{cid} references unknown primary_behavior: {behavior}")

        workflow = comp.get("workflow")
        if workflow and workflow not in known_workflow_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_WORKFLOW_REF", f"{cid} references unknown workflow: {workflow}")

        template = comp.get("template")
        if template and template not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_TEMPLATE_REF", f"{cid} references unknown template: {template}")

        for domain in comp.get("domains", []):
            if domain not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_DOMAIN_REF", f"{cid} references unknown domain: {domain}")

        for checklist in comp.get("checklists", []):
            if checklist not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_CHECKLIST_REF", f"{cid} references unknown checklist: {checklist}")

    if result["passed"]:
        add_msg(result, "info", "REFERENCE_CHECK_OK", "All checked references are valid")

    if not known_pack_ids:
        add_msg(result, "warning", "PACK_INDEX_EMPTY", "No pack ids found in registry/packs.json")

    return finalize_check_result(result, start)


# ============================================================
# Pack Routing Shape Validation
# ============================================================

def validate_pack_routing_shape(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    from .helpers import is_string_list, is_string_2d_list

    errors = []
    routing = pack.get("routing")
    if routing is None:
        return errors

    if not isinstance(routing, dict):
        errors.append({
            "code": "INVALID_PACK_ROUTING",
            "message": "routing must be an object",
        })
        return errors

    preferred_skill = routing.get("preferred_skill")
    if preferred_skill is not None and not isinstance(preferred_skill, str):
        errors.append({
            "code": "INVALID_PACK_ROUTING_PREFERRED_SKILL",
            "message": "routing.preferred_skill must be a string",
        })

    score_bonus = routing.get("score_bonus")
    if score_bonus is not None and not isinstance(score_bonus, int):
        errors.append({
            "code": "INVALID_PACK_ROUTING_SCORE_BONUS",
            "message": "routing.score_bonus must be an integer",
        })

    keywords_any = routing.get("keywords_any")
    if keywords_any is not None and not is_string_list(keywords_any):
        errors.append({
            "code": "INVALID_PACK_ROUTING_KEYWORDS_ANY",
            "message": "routing.keywords_any must be an array of strings",
        })

    keywords_all_groups = routing.get("keywords_all_groups")
    if keywords_all_groups is not None and not is_string_2d_list(keywords_all_groups):
        errors.append({
            "code": "INVALID_PACK_ROUTING_KEYWORDS_ALL_GROUPS",
            "message": "routing.keywords_all_groups must be an array of string arrays",
        })

    return errors


# ============================================================
# Check: Packs Validation
# ============================================================

def check_packs(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_PACKS, passed=True)
    jsonschema = _load_jsonschema()

    pd = packs_dir(root)
    if not pd.exists():
        result["passed"] = False
        add_msg(result, "error", "PACKS_DIR_MISSING", f"Packs directory not found: {pd}")
        return finalize_check_result(result, start)

    pack_files = sorted([p for p in pd.glob("*.json") if p.is_file()])
    if not pack_files:
        add_msg(result, "warning", "PACK_JSON_NOT_FOUND", "No pack JSON files found")
        return finalize_check_result(result, start)

    pack_schema_file = find_schema_file(root, "packs", ["packs.schema.json"])
    pack_schema = None

    if pack_schema_file:
        pack_schema, err = load_json_file_safe(pack_schema_file)
        if err:
            result["passed"] = False
            add_msg(result, "error", "INVALID_SCHEMA_JSON", f"Invalid pack schema JSON: {pack_schema_file.name}", err)
            pack_schema = None
        else:
            debug(ctx, f"Loaded pack schema: {pack_schema_file}")
            if jsonschema is not None:
                try:
                    validator_cls = jsonschema.validators.validator_for(pack_schema)
                    validator_cls.check_schema(pack_schema)
                except Exception as e:
                    result["passed"] = False
                    add_msg(result, "error", "INVALID_JSON_SCHEMA", f"Invalid JSON Schema: {pack_schema_file.name}", str(e))
                    pack_schema = None
    else:
        result["passed"] = False
        add_msg(result, "error", "PACK_SCHEMA_NOT_FOUND", "packs.schema.json not found")

    pack_index_items = load_pack_index(root)
    pack_index_by_id = {}

    for item in pack_index_items:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        if pid:
            pack_index_by_id[pid] = item

    if not pack_index_items:
        add_msg(result, "warning", "PACK_INDEX_EMPTY_OR_MISSING", "registry/packs.json is empty, missing, or not parseable as a pack list")

    disk_pack_ids = set()

    for pf in pack_files:
        rel_path = str(pf.relative_to(root)).replace("\\", "/")

        pack_data, err = load_json_file_safe(pf)
        if err:
            result["passed"] = False
            add_msg(result, "error", "INVALID_PACK_JSON", f"Invalid pack JSON: {pf.name}", err)
            continue

        debug(ctx, f"Loaded pack: {pf.name}")

        if not isinstance(pack_data, dict):
            result["passed"] = False
            add_msg(result, "error", "INVALID_PACK_FORMAT", f"Pack file must be a JSON object: {pf.name}")
            continue

        pid = pack_data.get("id")
        pname = pack_data.get("name")

        if pid:
            disk_pack_ids.add(pid)

        for required in ("id", "name"):
            if required not in pack_data:
                result["passed"] = False
                add_msg(result, "error", "PACK_MISSING_REQUIRED_FIELD", f"{pf.name} missing required field: {required}")

        routing_errors = validate_pack_routing_shape(pack_data)
        for routing_error in routing_errors:
            result["passed"] = False
            add_msg(result, "error", routing_error["code"], f"{pf.name}: {routing_error['message']}")

        if pack_schema and jsonschema is not None:
            errors = validate_instance_with_schema(pack_data, pack_schema)
            real_errors = [e for e in errors if e["code"] != "JSONSCHEMA_NOT_INSTALLED"]
            if real_errors:
                result["passed"] = False
                for e in real_errors:
                    add_msg(
                        result,
                        "error",
                        e["code"],
                        f"{pf.name} does not match {pack_schema_file.name}: {e['message']}",
                        {
                            "instance_path": e["path"],
                            "schema_path": e["schema_path"],
                        }
                    )
            else:
                add_msg(result, "info", "PACK_SCHEMA_VALID", f"{pf.name} matches {pack_schema_file.name}")

        if pid and pid not in pack_index_by_id:
            result["passed"] = False
            add_msg(result, "error", "PACK_NOT_INDEXED", f"{pf.name} ({pid}) not found in registry/packs.json")
        elif pid:
            index_item = pack_index_by_id[pid]
            index_path = index_item.get("path")
            if index_path and index_path != rel_path:
                result["passed"] = False
                add_msg(
                    result,
                    "error",
                    "PACK_INDEX_PATH_MISMATCH",
                    f"{pid} path mismatch between pack file and registry/packs.json",
                    {
                        "pack_file_path": rel_path,
                        "registry_path": index_path,
                    }
                )
            index_name = index_item.get("name")
            if pname and index_name and pname != index_name:
                add_msg(
                    result,
                    "warning",
                    "PACK_INDEX_NAME_MISMATCH",
                    f"{pid} name mismatch between pack file and registry/packs.json",
                    {
                        "pack_file_name": pname,
                        "registry_name": index_name,
                    }
                )

    for pid, item in pack_index_by_id.items():
        if pid not in disk_pack_ids:
            result["passed"] = False
            add_msg(result, "error", "PACK_INDEX_TARGET_MISSING", f"Indexed pack id not found on disk: {pid}")

    for pid, item in pack_index_by_id.items():
        path = item.get("path")
        if not path:
            continue
        full, path_error = resolve_registered_path(root, path)
        if path_error:
            result["passed"] = False
            add_msg(
                result,
                "error",
                path_error["code"],
                f"Registered pack path is invalid for {pid}: {path}",
                {"pack_id": pid, **path_error},
            )
        elif not full.exists():
            result["passed"] = False
            add_msg(
                result,
                "error",
                "PACK_INDEX_PATH_MISSING",
                f"Indexed pack path does not exist: {path}",
                {"pack_id": pid, "path": path},
            )

    return finalize_check_result(result, start)


# ============================================================
# Check: Pack Cross-References
# ============================================================

def check_pack_refs(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_PACK_REFS, passed=True)

    known_ids = collect_known_ids_from_modules_registry(root)
    workflows = load_array_registry(root, "workflows.json", ["workflows"])
    skills = load_array_registry(root, "skills.json", ["skills"])
    known_workflow_ids = {w.get("id") for w in workflows if isinstance(w, dict) and w.get("id")}
    known_skill_ids = {s.get("id") for s in skills if isinstance(s, dict) and s.get("id")}

    pd = packs_dir(root)
    if not pd.exists():
        result["passed"] = False
        add_msg(result, "error", "PACKS_DIR_MISSING", f"Packs directory not found: {pd}")
        return finalize_check_result(result, start)

    pack_files = sorted([p for p in pd.glob("*.json") if p.is_file()])
    if not pack_files:
        add_msg(result, "warning", "PACK_JSON_NOT_FOUND", "No pack JSON files found")
        return finalize_check_result(result, start)

    for pf in pack_files:
        pack, err = load_json_file_safe(pf)
        if err:
            result["passed"] = False
            add_msg(result, "error", "INVALID_PACK_JSON", f"Invalid pack JSON: {pf.name}", err)
            continue

        if not isinstance(pack, dict):
            result["passed"] = False
            add_msg(result, "error", "INVALID_PACK_FORMAT", f"Pack file must be object: {pf.name}")
            continue

        pid = pack.get("id", pf.stem)

        behavior = pack.get("behavior") or pack.get("primary_behavior")
        if behavior and behavior not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_PACK_BEHAVIOR_REF", f"{pid} references unknown behavior: {behavior}")

        workflow = pack.get("workflow")
        if workflow and workflow not in known_workflow_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_PACK_WORKFLOW_REF", f"{pid} references unknown workflow: {workflow}")

        template = pack.get("template")
        if template and template not in known_ids:
            result["passed"] = False
            add_msg(result, "error", "UNKNOWN_PACK_TEMPLATE_REF", f"{pid} references unknown template: {template}")

        for report in pack.get("reports", []):
            if report not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_PACK_REPORT_REF", f"{pid} references unknown report: {report}")

        for domain in pack.get("domains", []):
            if domain not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_PACK_DOMAIN_REF", f"{pid} references unknown domain: {domain}")

        for checklist in pack.get("checklists", []):
            if checklist not in known_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_PACK_CHECKLIST_REF", f"{pid} references unknown checklist: {checklist}")

        routing = pack.get("routing")
        if isinstance(routing, dict):
            preferred_skill = routing.get("preferred_skill")
            if preferred_skill and preferred_skill not in known_skill_ids:
                result["passed"] = False
                add_msg(result, "error", "UNKNOWN_PACK_ROUTING_SKILL_REF", f"{pid} routing references unknown skill: {preferred_skill}")

    if result["passed"]:
        add_msg(result, "info", "PACK_REFERENCE_CHECK_OK", "All checked pack references are valid")

    return finalize_check_result(result, start)


# ============================================================
# Check: API/Event Contract Compatibility
# ============================================================

def check_contracts(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_CONTRACTS, passed=True)

    from .contracts_validation import validate_contracts

    for issue in validate_contracts(root):
        result["passed"] = False
        add_msg(result, "error", issue["code"], issue["message"], issue.get("details"))

    if result["passed"]:
        add_msg(result, "info", "CONTRACT_CHECK_OK", "All declared API/event contract fixtures satisfy required compatibility directions")
    return finalize_check_result(result, start)


# ============================================================
# Check: Semantic Registry and Composition Validation
# ============================================================

def check_semantics(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_SEMANTICS, passed=True)

    from .semantic_validation import validate_semantics

    for issue in validate_semantics(root):
        result["passed"] = False
        add_msg(result, "error", issue["code"], issue["message"], issue.get("details"))

    if result["passed"]:
        add_msg(result, "info", "SEMANTIC_CHECK_OK", "All deterministic registry and composition invariants are valid")
    return finalize_check_result(result, start)


# ============================================================
# Check: Derived Module Registry Synchronization
# ============================================================

def check_derived_registry(root: Path, ctx) -> Dict[str, Any]:
    start = now_ms()
    result = make_check_result(CHECK_DERIVED_REGISTRY, passed=True)

    from .registry_generation import derived_registry_issues

    for issue in derived_registry_issues(root):
        result["passed"] = False
        add_msg(result, "error", issue["code"], issue["message"], {key: value for key, value in issue.items() if key not in {"code", "message"}})

    if result["passed"]:
        add_msg(result, "info", "DERIVED_REGISTRY_CHECK_OK", "All derived module registry identities are synchronized")
    return finalize_check_result(result, start)


# ============================================================
# Dispatch Map
# ============================================================

CHECK_RUNNERS = {
    CHECK_REGISTRY: check_registry,
    CHECK_PATHS: check_paths,
    CHECK_REFS: check_refs,
    CHECK_PACKS: check_packs,
    CHECK_PACK_REFS: check_pack_refs,
    CHECK_SEMANTICS: check_semantics,
    CHECK_CONTRACTS: check_contracts,
    CHECK_DERIVED_REGISTRY: check_derived_registry,
}
