# -*- coding: utf-8 -*-
"""Deterministic identity synchronization for selected module registry layers."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from .registry_discovery import load_array_registry, load_modules_registry


DERIVED_LAYERS = {
    "behaviors": ("behaviors.json", "behaviors"),
    "domains": ("domains.json", "domains"),
    "templates": ("templates.json", "templates"),
    "checklists": ("checklists.json", "checklists"),
    "reports": ("reports.json", "reports"),
}
IDENTITY_FIELDS = ("id", "path", "name")


def _by_id(items: Any, source: str) -> tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    issues: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return indexed, [{"code": "DERIVED_REGISTRY_INVALID_LAYER", "message": f"{source} must be an array"}]
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            issues.append({"code": "DERIVED_REGISTRY_INVALID_ENTRY", "message": f"{source} contains an entry without a valid id"})
            continue
        item_id = item["id"]
        if item_id in indexed:
            issues.append({"code": "DERIVED_REGISTRY_DUPLICATE_ID", "message": f"Duplicate id in {source}: {item_id}", "id": item_id})
            continue
        indexed[item_id] = item
    return indexed, issues


def build_expected_modules(root: Path) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Build modules.json with five layer identities projected from dedicated registries."""
    modules = deepcopy(load_modules_registry(root))
    layers = modules.get("layers")
    if not isinstance(layers, dict):
        return modules, [{"code": "DERIVED_REGISTRY_MODULES_INVALID", "message": "modules.json.layers must be an object"}]

    issues: List[Dict[str, Any]] = []
    for layer, (filename, key) in DERIVED_LAYERS.items():
        dedicated, dedicated_issues = _by_id(load_array_registry(root, filename, [key]), filename)
        existing, existing_issues = _by_id(layers.get(layer), f"modules.json.layers.{layer}")
        issues.extend(dedicated_issues)
        issues.extend(existing_issues)
        if dedicated_issues or existing_issues:
            continue

        expected_entries = []
        for item_id, entry in dedicated.items():
            overlay = existing.get(item_id)
            expected = deepcopy(overlay) if overlay is not None else {"role": "derived-module"}
            for field in IDENTITY_FIELDS:
                value = entry.get(field)
                if not isinstance(value, str) or not value:
                    issues.append({"code": "DERIVED_REGISTRY_INVALID_ENTRY", "message": f"{filename} entry {item_id} has invalid {field}", "layer": layer, "id": item_id, "field": field})
                else:
                    expected[field] = value
            expected_entries.append(expected)

        for item_id in existing:
            if item_id not in dedicated:
                issues.append({"code": "DERIVED_REGISTRY_ENTRY_ORPHAN", "message": f"{item_id} has no dedicated registry entry for {layer}", "layer": layer, "id": item_id})

        if not any(issue.get("layer") == layer for issue in issues):
            layers[layer] = expected_entries

    return modules, issues


def derived_registry_issues(root: Path) -> List[Dict[str, Any]]:
    actual = load_modules_registry(root)
    expected, issues = build_expected_modules(root)
    if issues:
        return issues

    actual_layers = actual.get("layers", {})
    expected_layers = expected.get("layers", {})
    for layer in DERIVED_LAYERS:
        actual_items = actual_layers.get(layer, [])
        expected_items = expected_layers.get(layer, [])
        if actual_items != expected_items:
            actual_by_id, _ = _by_id(actual_items, f"modules.json.layers.{layer}")
            expected_by_id, _ = _by_id(expected_items, f"expected.modules.layers.{layer}")
            for item_id in expected_by_id:
                if item_id not in actual_by_id:
                    issues.append({"code": "DERIVED_REGISTRY_ENTRY_MISSING", "message": f"{item_id} is missing from modules.json.layers.{layer}", "layer": layer, "id": item_id})
                    continue
                for field in IDENTITY_FIELDS:
                    if actual_by_id[item_id].get(field) != expected_by_id[item_id].get(field):
                        issues.append({"code": "DERIVED_REGISTRY_IDENTITY_MISMATCH", "message": f"{item_id} has a different {field} in modules.json.layers.{layer}", "layer": layer, "id": item_id, "field": field, "actual": actual_by_id[item_id].get(field), "expected": expected_by_id[item_id].get(field)})
            for item_id in actual_by_id:
                if item_id not in expected_by_id:
                    issues.append({"code": "DERIVED_REGISTRY_ENTRY_ORPHAN", "message": f"{item_id} has no dedicated registry entry for {layer}", "layer": layer, "id": item_id})
    return issues


def write_synced_modules(root: Path) -> List[Dict[str, Any]]:
    expected, issues = build_expected_modules(root)
    if issues:
        return issues
    (root / "registry" / "modules.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []
