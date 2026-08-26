# -*- coding: utf-8 -*-
"""Tests for fixture-backed API/event contract compatibility validation."""

import json
import shutil
from pathlib import Path

from click.testing import CliRunner

import forge_cli.contracts_validation as contracts_validation
from forge_cli.cli import cli
from forge_cli.contracts_validation import validate_contracts


def _copy_root(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "forge"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "out"))
    return target


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_real_contract_catalog_is_valid():
    root = Path(__file__).resolve().parents[1]
    assert validate_contracts(root) == []


def test_contract_validation_fails_closed_without_jsonschema(tmp_path, monkeypatch):
    root = _copy_root(tmp_path)
    monkeypatch.setattr(contracts_validation, "find_spec", lambda _: None)

    assert validate_contracts(root) == [{
        "code": "CONTRACT_JSONSCHEMA_UNAVAILABLE",
        "message": "jsonschema is required for contract compatibility validation",
    }]


def test_contract_validation_detects_directional_break(tmp_path):
    root = _copy_root(tmp_path)
    schema_path = root / "artifacts" / "contracts" / "customer-api" / "current.schema.json"
    schema = _load(schema_path)
    schema["required"].append("display_name")
    _write(schema_path, schema)

    codes = {issue["code"] for issue in validate_contracts(root)}

    assert "CONTRACT_BASELINE_TO_CURRENT_BREAK" in codes


def test_contract_validation_detects_invalid_fixture_acceptance(tmp_path):
    root = _copy_root(tmp_path)
    fixture_path = root / "tests" / "fixtures" / "contracts" / "customer-api" / "invalid" / "missing-id.json"
    _write(fixture_path, {"id": "customer-1", "name": "Ada"})

    codes = {issue["code"] for issue in validate_contracts(root)}

    assert "CONTRACT_INVALID_FIXTURE_ACCEPTED" in codes


def test_contract_validation_rejects_missing_and_escaping_paths(tmp_path):
    root = _copy_root(tmp_path)
    catalog_path = root / "registry" / "contracts.json"
    catalog = _load(catalog_path)
    catalog["contracts"][0]["baseline_schema"] = "../outside.json"
    _write(catalog_path, catalog)

    issues = validate_contracts(root)
    assert issues[0]["code"] == "CONTRACT_PATH_ESCAPE"


def test_cli_contract_check_and_default_validation_include_contracts(tmp_path):
    root = _copy_root(tmp_path)
    runner = CliRunner()

    focused = runner.invoke(cli, ["--root", str(root), "--format", "json", "validate", "--check", "contracts"])
    focused_payload = json.loads(focused.output)
    assert focused.exit_code == 0
    assert focused_payload["checks"][0]["name"] == "contracts"

    complete = runner.invoke(cli, ["--root", str(root), "--format", "json", "validate"])
    complete_payload = json.loads(complete.output)
    assert "contracts" in [check["name"] for check in complete_payload["checks"]]
