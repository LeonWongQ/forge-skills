# -*- coding: utf-8 -*-
"""Forge CLI — query and listing helpers for registry items."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .helpers import normalize_text, safe_name_to_id_suffix
from .registry_discovery import (
    load_array_registry,
    load_modules_registry,
    load_pack_objects,
)


def list_modules_by_kind(root: Path, kind: str) -> List[Dict[str, Any]]:
    if kind in ("modules", "all"):
        data = load_modules_registry(root)
        results = []
        layers = data.get("layers", {})
        if isinstance(layers, dict):
            for _, items in layers.items():
                if isinstance(items, list):
                    results.extend(items)
        return results

    if kind == "skills":
        return load_array_registry(root, "skills.json", ["skills"])
    if kind == "packs":
        return load_array_registry(root, "packs.json", ["packs"])
    if kind == "workflows":
        return load_array_registry(root, "workflows.json", ["workflows"])
    if kind == "compositions":
        return load_array_registry(root, "compositions.json", ["compositions"])

    modules = load_modules_registry(root)
    layers = modules.get("layers", {})
    if isinstance(layers, dict) and kind in layers and isinstance(layers[kind], list):
        return layers[kind]

    registry_filename_map = {
        "behaviors": "behaviors.json",
        "domains": "domains.json",
        "templates": "templates.json",
        "checklists": "checklists.json",
        "reports": "reports.json",
    }

    filename = registry_filename_map.get(kind)
    if filename:
        return load_array_registry(root, filename, [kind])

    return []


def find_item(root: Path, item_type: str, query: str) -> Optional[Dict[str, Any]]:
    items = list_modules_by_kind(root, item_type)
    normalized = query.strip()

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("id") == normalized:
            return item
        if item.get("name") == normalized:
            return item

        if item_type == "skills":
            suffix = safe_name_to_id_suffix(normalized)
            if item.get("id") == f"skill.{suffix}":
                return item

        if item_type == "packs":
            suffix = safe_name_to_id_suffix(normalized)
            if item.get("id") == f"pack.{suffix}":
                return item

    return None


def find_skill_by_query(root: Path, query: str) -> Optional[Dict[str, Any]]:
    return find_item(root, "skills", query)


def find_pack_by_query(root: Path, query: str) -> Optional[Dict[str, Any]]:
    item = find_item(root, "packs", query)
    if item:
        return item

    suffix = safe_name_to_id_suffix(query.strip())
    target_ids = {query.strip(), f"pack.{suffix}"}

    for pack in load_pack_objects(root):
        if pack.get("id") in target_ids or pack.get("name") == query.strip():
            return pack

    return None


def find_pack_object_by_id(root: Path, pack_id: str) -> Optional[Dict[str, Any]]:
    for pack in load_pack_objects(root):
        if pack.get("id") == pack_id:
            return pack
    return None


def contains_any(text: str, keywords: List[str]) -> List[str]:
    t = normalize_text(text)
    hits = []
    for kw in keywords:
        if normalize_text(kw) in t:
            hits.append(kw)
    return sorted(set(hits))


def match_all_keyword_groups(text: str, groups: List[List[str]]) -> Tuple[bool, List[str]]:
    t = normalize_text(text)
    all_hits = []
    for group in groups:
        group_hits = [kw for kw in group if normalize_text(kw) in t]
        if not group_hits:
            return False, []
        all_hits.extend(group_hits)
    return True, sorted(set(all_hits))
