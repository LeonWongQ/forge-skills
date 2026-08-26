# -*- coding: utf-8 -*-
"""Fixture-backed JSON Schema API/event contract compatibility validation."""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from importlib.util import find_spec

from .helpers import load_json_file_safe
from .registry_discovery import validate_instance_with_schema


def _issue(code: str, message: str, **details: Any) -> Dict[str, Any]:
    result = {"code": code, "message": message}
    if details:
        result["details"] = details
    return result


def _resolve(root: Path, value: str) -> Tuple[Path | None, Dict[str, Any] | None]:
    candidate = (root / value.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, _issue("CONTRACT_PATH_ESCAPE", f"Contract path escapes Forge root: {value}", path=value)
    if not candidate.exists():
        return None, _issue("CONTRACT_PATH_MISSING", f"Contract path does not exist: {value}", path=value)
    return candidate, None


def _load_json(root: Path, value: str, kind: str) -> Tuple[Any, Dict[str, Any] | None]:
    path, error = _resolve(root, value)
    if error:
        return None, error
    data, error_text = load_json_file_safe(path)
    if error_text:
        return None, _issue(f"CONTRACT_{kind}_INVALID_JSON", f"Cannot load {kind.lower()}: {value}", path=value, error=error_text)
    return data, None


def _validate_fixture(schema: Dict[str, Any], fixture: Any) -> List[Dict[str, Any]]:
    return [error for error in validate_instance_with_schema(fixture, schema) if error["code"] != "JSONSCHEMA_NOT_INSTALLED"]


def validate_contracts(root: Path) -> List[Dict[str, Any]]:
    if find_spec("jsonschema") is None:
        return [_issue("CONTRACT_JSONSCHEMA_UNAVAILABLE", "jsonschema is required for contract compatibility validation")]
    catalog, catalog_error = _load_json(root, "registry/contracts.json", "CATALOG")
    if catalog_error:
        return [catalog_error]
    if not isinstance(catalog, dict) or not isinstance(catalog.get("contracts"), list):
        return [_issue("CONTRACT_CATALOG_INVALID", "Contract catalog must contain a contracts list")]

    issues: List[Dict[str, Any]] = []
    seen_ids = set()
    for contract in catalog["contracts"]:
        if not isinstance(contract, dict):
            issues.append(_issue("CONTRACT_ENTRY_INVALID", "Contract entry must be an object"))
            continue
        contract_id = contract.get("id", "<unknown>")
        if contract_id in seen_ids:
            issues.append(_issue("CONTRACT_DUPLICATE_ID", f"Duplicate contract id: {contract_id}", contract=contract_id))
            continue
        seen_ids.add(contract_id)

        baseline, error = _load_json(root, contract.get("baseline_schema", ""), "SCHEMA")
        if error:
            issues.append(_issue(error["code"], error["message"], contract=contract_id, **error.get("details", {})))
            continue
        current, error = _load_json(root, contract.get("current_schema", ""), "SCHEMA")
        if error:
            issues.append(_issue(error["code"], error["message"], contract=contract_id, **error.get("details", {})))
            continue
        if not isinstance(baseline, dict) or not isinstance(current, dict):
            issues.append(_issue("CONTRACT_SCHEMA_INVALID", f"{contract_id} schemas must be JSON objects", contract=contract_id))
            continue

        fixtures = contract.get("fixtures", {})
        compatibility = contract.get("compatibility", {})
        for group in ("baseline_valid", "current_valid", "invalid"):
            paths = fixtures.get(group, []) if isinstance(fixtures, dict) else []
            if not isinstance(paths, list):
                issues.append(_issue("CONTRACT_FIXTURE_GROUP_INVALID", f"{contract_id} fixture group {group} must be a list", contract=contract_id, group=group))
                continue
            if group == "baseline_valid" and compatibility.get("baseline_to_current") == "required" and not paths:
                issues.append(_issue("CONTRACT_REQUIRED_FIXTURES_EMPTY", f"{contract_id} requires baseline_valid fixtures", contract=contract_id, group=group))
            if group == "current_valid" and compatibility.get("current_to_baseline") == "required" and not paths:
                issues.append(_issue("CONTRACT_REQUIRED_FIXTURES_EMPTY", f"{contract_id} requires current_valid fixtures", contract=contract_id, group=group))
            for fixture_path in paths:
                fixture, fixture_error = _load_json(root, fixture_path, "FIXTURE")
                if fixture_error:
                    issues.append(_issue(fixture_error["code"], fixture_error["message"], contract=contract_id, fixture=fixture_path, **fixture_error.get("details", {})))
                    continue
                baseline_errors = _validate_fixture(baseline, fixture)
                current_errors = _validate_fixture(current, fixture)
                if group == "baseline_valid":
                    if baseline_errors:
                        issues.append(_issue("CONTRACT_BASELINE_FIXTURE_INVALID", f"{contract_id} baseline fixture fails baseline schema: {fixture_path}", contract=contract_id, fixture=fixture_path))
                    if compatibility.get("baseline_to_current") == "required" and current_errors:
                        issues.append(_issue("CONTRACT_BASELINE_TO_CURRENT_BREAK", f"{contract_id} current schema rejects baseline fixture: {fixture_path}", contract=contract_id, fixture=fixture_path))
                elif group == "current_valid":
                    if current_errors:
                        issues.append(_issue("CONTRACT_CURRENT_FIXTURE_INVALID", f"{contract_id} current fixture fails current schema: {fixture_path}", contract=contract_id, fixture=fixture_path))
                    if compatibility.get("current_to_baseline") == "required" and baseline_errors:
                        issues.append(_issue("CONTRACT_CURRENT_TO_BASELINE_BREAK", f"{contract_id} baseline schema rejects current fixture: {fixture_path}", contract=contract_id, fixture=fixture_path))
                elif group == "invalid" and (not baseline_errors or not current_errors):
                    issues.append(_issue("CONTRACT_INVALID_FIXTURE_ACCEPTED", f"{contract_id} invalid fixture is accepted by a contract schema: {fixture_path}", contract=contract_id, fixture=fixture_path))

    return sorted(issues, key=lambda item: (item["code"], item["message"]))
