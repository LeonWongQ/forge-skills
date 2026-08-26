# -*- coding: utf-8 -*-
"""Canonical route/recommend regression loading, evaluation, and summaries."""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import jsonschema
except ImportError:
    jsonschema = None


CONFIDENCE_ORDER = {"low": 1, "medium": 2, "high": 3}


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_regression_cases(root: Path) -> List[Dict[str, Any]]:
    regression_file = root / "registry" / "route-regression.json"
    schema_file = root / "registry" / "schemas" / "route-regression.schema.json"
    if not regression_file.exists() or not schema_file.exists():
        raise RuntimeError("Route regression catalog or schema is missing")
    if jsonschema is None:
        raise RuntimeError("jsonschema is not installed, cannot validate route-regression.json schema")
    data, schema = load_json(regression_file), load_json(schema_file)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    errors = sorted(validator_cls(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        raise RuntimeError("route-regression.json schema validation failed:\n" + "\n".join(error.message for error in errors))
    return data["cases"]


def _actual_skill(result: Dict[str, Any], mode: str) -> Optional[str]:
    return ((result.get("skill") or {}).get("id") if mode == "route" else (result.get("recommended") or {}).get("skill"))


def _actual_pack(result: Dict[str, Any], mode: str) -> Optional[str]:
    return ((result.get("pack") or {}).get("id") if mode == "route" else (result.get("recommended") or {}).get("pack"))


def _actual_variant(result: Dict[str, Any], mode: str) -> Optional[str]:
    return result.get("variant") if mode == "route" else (result.get("recommended") or {}).get("variant")


def _actual_domains(result: Dict[str, Any], mode: str) -> List[str]:
    return result.get("domains", []) if mode == "route" else (result.get("recommended") or {}).get("domains", [])


def _in_confidence_range(actual: Optional[str], bounds: Dict[str, str]) -> bool:
    return actual in CONFIDENCE_ORDER and CONFIDENCE_ORDER[bounds["min"]] <= CONFIDENCE_ORDER[actual] <= CONFIDENCE_ORDER[bounds["max"]]


def evaluate_regression_case(case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    expected, mode = case["expected"], case["mode"]
    actual_skill, actual_pack = _actual_skill(result, mode), _actual_pack(result, mode)
    actual_variant, actual_domains = _actual_variant(result, mode), _actual_domains(result, mode)
    actual_matched, actual_confidence = result.get("matched"), result.get("confidence")
    actual_diagnostics = result.get("confidence_diagnostics")
    actual_native = (result.get("native") or {}).get("id")
    reason = result.get("reason")
    actual_reason_code = reason.get("code") if isinstance(reason, dict) else None
    errors = []
    if actual_matched != expected["matched"]:
        errors.append(f"Expected matched={expected['matched']}, actual={actual_matched}")
    if "skill" in expected and actual_skill != expected["skill"]:
        errors.append(f"Expected skill={expected['skill']}, actual={actual_skill}")
    if "pack" in expected and actual_pack != expected["pack"]:
        errors.append(f"Expected pack={expected['pack']}, actual={actual_pack}")
    if "decision" in expected and result.get("decision") != expected["decision"]:
        errors.append(f"Expected decision={expected['decision']}, actual={result.get('decision')}")
    if "host_action" in expected and result.get("host_action") != expected["host_action"]:
        errors.append(f"Expected host_action={expected['host_action']}, actual={result.get('host_action')}")
    if "reason_code" in expected and actual_reason_code != expected["reason_code"]:
        errors.append(f"Expected reason.code={expected['reason_code']}, actual={actual_reason_code}")
    if "native_id" in expected and actual_native != expected["native_id"]:
        errors.append(f"Expected native_id={expected['native_id']}, actual={actual_native}")
    if "variant" in expected and actual_variant != expected["variant"]:
        errors.append(f"Expected variant={expected['variant']}, actual={actual_variant}")
    if "domains" in expected and actual_domains != expected["domains"]:
        errors.append(f"Expected domains={expected['domains']}, actual={actual_domains}")
    for domain in expected.get("forbidden_domains", []):
        if domain in actual_domains:
            errors.append(f"Forbidden domain present: {domain}")
    if not _in_confidence_range(actual_confidence, expected["confidence"]):
        errors.append(f"Expected confidence in {expected['confidence']}, actual={actual_confidence}")
    for key, value in expected.get("diagnostics", {}).items():
        actual_value = actual_diagnostics.get(key) if isinstance(actual_diagnostics, dict) else None
        if actual_value != value:
            errors.append(f"Expected diagnostics.{key}={value}, actual={actual_value}")
    if actual_skill in expected.get("forbidden_skills", []):
        errors.append(f"Forbidden skill matched: {actual_skill}")
    if actual_pack in expected.get("forbidden_packs", []):
        errors.append(f"Forbidden pack matched: {actual_pack}")
    return {"id": case["id"], "mode": mode, "category": case["category"], "input": case["input"], "passed": not errors, "errors": errors, "actual": {"matched": actual_matched, "skill": actual_skill, "pack": actual_pack, "confidence": actual_confidence, "diagnostics": result.get("confidence_diagnostics")}}


def summarize_regression_results(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    def counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
        return {"passed": sum(item["passed"] for item in items), "failed": sum(not item["passed"] for item in items), "total": len(items)}
    categories = sorted(set(item["category"] for item in evaluations))
    modes = sorted(set(item["mode"] for item in evaluations))
    return {"total": counts(evaluations), "by_mode": {mode: counts([item for item in evaluations if item["mode"] == mode]) for mode in modes}, "by_category": {category: counts([item for item in evaluations if item["category"] == category]) for category in categories}, "confidence_distribution": dict(sorted(Counter(item["actual"]["confidence"] for item in evaluations).items()))}
