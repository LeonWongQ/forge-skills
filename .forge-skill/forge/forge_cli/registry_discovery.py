# -*- coding: utf-8 -*-
"""Forge CLI — registry discovery: schema loading, JSON parsing, ID collection."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .helpers import (
    format_exception_path,
    load_json,
    load_json_file_safe,
)


def registry_dir(root: Path) -> Path:
    return root / "registry"


def schemas_dir(root: Path) -> Path:
    return root / "registry" / "schemas"


def packs_dir(root: Path) -> Path:
    return root / "packs"


def get_registry_json_files(root: Path) -> List[Path]:
    rd = registry_dir(root)
    if not rd.exists():
        return []
    return sorted([p for p in rd.glob("*.json") if p.is_file()])


def get_schema_files(root: Path) -> List[Path]:
    sd = schemas_dir(root)
    if not sd.exists():
        return []
    return sorted([p for p in sd.glob("*.json") if p.is_file()])


def build_schema_map(root: Path) -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    for sf in get_schema_files(root):
        name = sf.name
        normalized = name
        if normalized.endswith(".schema.json"):
            normalized = normalized[:-len(".schema.json")]
        elif normalized.endswith(".json"):
            normalized = normalized[:-len(".json")]
        result[normalized] = sf
    return result


def find_schema_file(root: Path, logical_name: str, candidates: List[str]) -> Optional[Path]:
    sd = schemas_dir(root)
    if not sd.exists():
        return None

    for c in candidates:
        direct = sd / c
        if direct.exists():
            return direct

    schema_map = build_schema_map(root)
    for c in candidates:
        normalized = c
        if normalized.endswith(".schema.json"):
            normalized = normalized[:-len(".schema.json")]
        elif normalized.endswith(".json"):
            normalized = normalized[:-len(".json")]
        if normalized in schema_map:
            return schema_map[normalized]

    if logical_name in schema_map:
        return schema_map[logical_name]

    return None


@lru_cache(maxsize=32)
def _load_skill_routing_config(path: str) -> Dict[str, Any]:
    """Read one routing configuration once per CLI process and root."""
    data = load_json(Path(path))
    return data if isinstance(data, dict) else {}


def load_skill_routing_config(root: Path) -> Dict[str, Any]:
    path = root / "registry" / "skill-routing.json"
    if not path.is_file():
        return {}
    return _load_skill_routing_config(str(path))


def validate_instance_with_schema(instance: Any, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []

    try:
        import jsonschema
    except ImportError:
        jsonschema = None

    if jsonschema is None:
        errors.append({
            "code": "JSONSCHEMA_NOT_INSTALLED",
            "message": "jsonschema not installed; schema validation skipped",
            "path": "$",
            "schema_path": "$",
        })
        return errors

    try:
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
            errors.append({
                "code": "SCHEMA_VALIDATION_ERROR",
                "message": err.message,
                "path": format_exception_path("$", list(err.path)),
                "schema_path": format_exception_path("$", list(err.schema_path)),
            })
    except jsonschema.exceptions.SchemaError as e:
        errors.append({
            "code": "INVALID_SCHEMA",
            "message": str(e),
            "path": "$",
            "schema_path": "$",
        })
    except Exception as e:
        errors.append({
            "code": "SCHEMA_VALIDATION_EXCEPTION",
            "message": str(e),
            "path": "$",
            "schema_path": "$",
        })

    return errors


def load_project_metadata(root: Path) -> Dict[str, Any]:
    project_file = root / "registry" / "project.json"
    if project_file.exists():
        data = load_json(project_file)
        return {
            "name": data.get("name", "forge"),
            "version": data.get("version", "unknown"),
            "description": data.get("description"),
            # Consumer-facing metadata must not expose an installation target.
            "source": "registry/project.json",
        }

    return {
        "name": "forge",
        "version": "unknown",
        "description": None,
        "source": "fallback",
    }


def load_modules_registry(root: Path) -> Dict[str, Any]:
    f = root / "registry" / "modules.json"
    if f.exists():
        return load_json(f)
    return {}


def load_array_registry(root: Path, filename: str, top_level_keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    f = root / "registry" / filename
    if not f.exists():
        return []

    data = load_json(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if top_level_keys:
            for key in top_level_keys:
                value = data.get(key)
                if isinstance(value, list):
                    return value

        for value in data.values():
            if isinstance(value, list):
                return value

    return []


def load_pack_index(root: Path) -> List[Dict[str, Any]]:
    return load_array_registry(root, "packs.json", ["packs"])


def load_pack_objects(root: Path) -> List[Dict[str, Any]]:
    pd = packs_dir(root)
    if not pd.exists():
        return []

    results = []
    for pf in sorted([p for p in pd.glob("*.json") if p.is_file()]):
        data, err = load_json_file_safe(pf)
        if err or not isinstance(data, dict):
            continue
        data["_file"] = str(pf)
        results.append(data)
    return results


def collect_known_ids_from_modules_registry(root: Path) -> Set[str]:
    known_ids: Set[str] = set()

    modules = load_modules_registry(root)
    layers = modules.get("layers", {})
    if isinstance(layers, dict):
        for _, items in layers.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("id"):
                        known_ids.add(item["id"])

    dedicated = [
        ("skills.json", ["skills"]),
        ("behaviors.json", ["behaviors"]),
        ("domains.json", ["domains"]),
        ("templates.json", ["templates"]),
        ("checklists.json", ["checklists"]),
        ("reports.json", ["reports"]),
        ("workflows.json", ["workflows"]),
        ("compositions.json", ["compositions"]),
        ("packs.json", ["packs"]),
    ]

    for filename, keys in dedicated:
        items = load_array_registry(root, filename, keys)
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                known_ids.add(item["id"])

    return known_ids
