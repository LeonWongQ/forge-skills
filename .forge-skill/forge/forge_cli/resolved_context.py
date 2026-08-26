# -*- coding: utf-8 -*-
"""Build read-only, registry-resolved Forge context manifests."""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .helpers import portable_path_from_forge_root, resolve_registered_path
from .query_helpers import find_item, find_pack_object_by_id, list_modules_by_kind
from .registry_discovery import load_pack_index, load_project_metadata
from .routing_engine import build_recommendation_from_route


SCHEMA_VERSION = "1.0"


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def _module_index(root: Path) -> Dict[str, Dict[str, Any]]:
    return {
        item["id"]: item
        for item in list_modules_by_kind(root, "modules")
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _workspace_relative(root: Path, path: Path) -> str:
    return portable_path_from_forge_root(root, path)


def _resolved_entry(
    root: Path,
    item_id: str,
    layer: str,
    entry: Optional[Dict[str, Any]],
    sources: List[str],
) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    declared_path = entry.get("path") if isinstance(entry, dict) else None
    result: Dict[str, Any] = {
        "id": item_id,
        "layer": layer,
        "name": entry.get("name") if isinstance(entry, dict) else None,
        "declared_path": declared_path,
        "resolved_path": None,
        "exists": False,
        "sources": sources,
    }
    if entry is None:
        return result, {
            "code": "CONTEXT_MODULE_UNKNOWN",
            "message": f"Selected module is not registered: {item_id}",
            "id": item_id,
        }
    if declared_path is None:
        return result, {
            "code": "CONTEXT_MODULE_PATH_MISSING",
            "message": f"Selected module has no registered path: {item_id}",
            "id": item_id,
        }

    path, path_error = resolve_registered_path(root, declared_path)
    if path_error:
        return result, {
            **path_error,
            "message": f"Selected module has an unsafe registered path: {item_id}",
            "id": item_id,
        }
    assert path is not None
    result["resolved_path"] = _workspace_relative(root, path)
    result["exists"] = path.exists()
    if not result["exists"]:
        return result, {
            "code": "CONTEXT_MODULE_PATH_NOT_FOUND",
            "message": f"Selected module path does not exist: {item_id}",
            "id": item_id,
            "path": declared_path,
        }
    return result, None


def _selection_from_route(route_result: Dict[str, Any]) -> Dict[str, Any]:
    recommended = build_recommendation_from_route(route_result).get("recommended") or {}
    return {
        "matched": route_result.get("matched", False),
        "input": route_result.get("input"),
        "strategy": route_result.get("strategy"),
        "confidence": route_result.get("confidence"),
        "confidence_diagnostics": route_result.get("confidence_diagnostics"),
        "skill": recommended.get("skill"),
        "variant": recommended.get("variant"),
        "pack": recommended.get("pack"),
        "behavior": recommended.get("behavior"),
        "workflow": recommended.get("workflow"),
        "template": recommended.get("template"),
        "domains": recommended.get("domains", []),
        "checklists": recommended.get("checklists", []),
        "evidence": route_result.get("evidence", []),
        "pack_evidence": route_result.get("pack_evidence", []),
        "warnings": route_result.get("warnings", []),
        "unresolved": {},
    }


def _selection_from_compose(compose_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "matched": bool(compose_result.get("matched")),
        "skill": compose_result.get("skill"),
        "pack": compose_result.get("pack"),
        "behavior": compose_result.get("behavior"),
        "workflow": compose_result.get("workflow"),
        "template": compose_result.get("template"),
        "domains": compose_result.get("domains", []),
        "checklists": compose_result.get("checklists", []),
        "sources": compose_result.get("sources", {}),
        "warnings": compose_result.get("warnings", []),
        "unresolved": compose_result.get("unresolved", {}),
    }


def build_resolved_context(root: Path, selection: Dict[str, Any], mode: str, source: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a final selection into registered module identities and safe paths."""
    module_index = _module_index(root)
    pack_index = {item.get("id"): item for item in load_pack_index(root) if isinstance(item, dict)}
    workflow_index = {
        item.get("id"): item
        for item in list_modules_by_kind(root, "workflows")
        if isinstance(item, dict)
    }
    errors: List[Dict[str, Any]] = []
    warnings = list(selection.get("warnings", []))
    context: Dict[str, List[Dict[str, Any]]] = {
        layer: []
        for layer in ("kernel", "runtime", "skills", "packs", "behaviors", "workflow", "engine", "domains", "templates", "checklists", "reports")
    }
    seen: Dict[str, set[str]] = {layer: set() for layer in context}

    def add(layer: str, item_id: Optional[str], sources: List[str], entry: Optional[Dict[str, Any]] = None) -> None:
        if not item_id or item_id in seen[layer]:
            return
        seen[layer].add(item_id)
        resolved, error = _resolved_entry(root, item_id, layer, entry or module_index.get(item_id), sources)
        context[layer].append(resolved)
        if error:
            errors.append(error)

    if selection.get("matched"):
        add("kernel", "kernel.claude", ["baseline"])
        add("runtime", "runtime.router", ["baseline"])
        add("skills", selection.get("skill"), ["selection"])
        pack_id = selection.get("pack")
        if pack_id:
            add("packs", pack_id, ["selection"], pack_index.get(pack_id))
        add("behaviors", selection.get("behavior"), ["selection"])
        add("templates", selection.get("template"), ["selection"])
        for domain in _unique(selection.get("domains", [])):
            add("domains", domain, ["selection"])
        for checklist in _unique(selection.get("checklists", [])):
            add("checklists", checklist, ["selection"])

        workflow_id = selection.get("workflow")
        if workflow_id:
            workflow = workflow_index.get(workflow_id)
            if workflow is None:
                errors.append({"code": "CONTEXT_WORKFLOW_UNKNOWN", "message": f"Selected workflow is not registered: {workflow_id}", "id": workflow_id})
            else:
                context["workflow"].append({"id": workflow_id, "layer": "workflow", "name": workflow.get("name"), "stages": workflow.get("stages", []), "sources": ["selection"]})
                for stage in workflow.get("stages", []):
                    add("engine", stage, ["workflow"])

        pack = find_pack_object_by_id(root, pack_id) if pack_id else None
        if pack:
            pack_modules = pack.get("modules", {})
            for item_id in _unique(pack_modules.get("kernel", [])):
                add("kernel", item_id, ["pack.modules.kernel"])
            for item_id in _unique(pack_modules.get("runtime", [])):
                add("runtime", item_id, ["pack.modules.runtime"])
            for item_id in _unique(pack_modules.get("behaviors", [])):
                add("behaviors", item_id, ["pack.modules.behaviors"])
            for item_id in _unique(pack_modules.get("domains", [])):
                add("domains", item_id, ["pack.modules.domains"])
            for item_id in _unique(pack_modules.get("engine", [])):
                add("engine", item_id, ["pack.modules.engine"])
            for item_id in _unique(pack.get("reports", [])):
                add("reports", item_id, ["pack.reports"])

    if not selection.get("matched"):
        errors.append({"code": "CONTEXT_SELECTION_UNMATCHED", "message": "No selection was available to resolve"})
    if selection.get("unresolved"):
        errors.append({"code": "CONTEXT_SELECTION_UNRESOLVED", "message": "Explicit selection contained unresolved identifiers", "unresolved": selection["unresolved"]})

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "project": load_project_metadata(root),
        "source": source,
        "selection": selection,
        "context": context,
        "resolution": {"ok": not errors, "errors": errors, "warnings": warnings},
    }


def build_context_from_route(root: Path, route_result: Dict[str, Any]) -> Dict[str, Any]:
    selection = _selection_from_route(route_result)
    return build_resolved_context(root, selection, "resolve", {"kind": "route", "input": route_result.get("input")})


def build_context_from_compose(root: Path, compose_result: Dict[str, Any]) -> Dict[str, Any]:
    selection = _selection_from_compose(compose_result)
    return build_resolved_context(root, selection, "resolve", {"kind": "compose"})
