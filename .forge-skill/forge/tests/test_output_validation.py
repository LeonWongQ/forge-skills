# -*- coding: utf-8 -*-
"""Tests for template-bound structured output validation."""

import json
from pathlib import Path

from click.testing import CliRunner

from forge_cli.cli import cli
from forge_cli.output_validation import validate_template_output


def _write_contract_root(root: Path, *, schema_path: str = "registry/schemas/output.schema.json", bindings=None):
    (root / "registry" / "schemas").mkdir(parents=True, exist_ok=True)
    binding_items = bindings if bindings is not None else [
        {"template_id": "template.default", "schema": schema_path},
    ]
    (root / "registry" / "template-outputs.json").write_text(
        json.dumps({"template_outputs": binding_items}), encoding="utf-8"
    )
    if schema_path == "registry/schemas/output.schema.json":
        (root / "registry" / "schemas" / "output.schema.json").write_text(
            json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            }),
            encoding="utf-8",
        )


def test_validate_output_json_success(forge_root, tmp_path):
    _write_contract_root(forge_root)
    input_path = tmp_path / "output.json"
    input_path.write_text(json.dumps({"result": "ok"}), encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["--root", str(forge_root), "--format", "json", "validate-output", "--template", "template.default", "--input", str(input_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["schema_path"] == "registry/schemas/output.schema.json"
    assert payload["errors"] == []


def test_validate_output_reports_sorted_schema_errors(forge_root, tmp_path):
    _write_contract_root(forge_root)
    input_path = tmp_path / "output.json"
    input_path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")

    payload = validate_template_output(forge_root, "template.default", input_path)

    assert payload["valid"] is False
    assert [error["code"] for error in payload["errors"]] == [
        "SCHEMA_VALIDATION_ERROR",
        "SCHEMA_VALIDATION_ERROR",
    ]
    assert payload["errors"][0]["path"] == "$"
    assert payload["errors"][1]["path"] == "$"


def test_validate_output_rejects_unknown_template(forge_root, tmp_path):
    _write_contract_root(forge_root)
    input_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")

    payload = validate_template_output(forge_root, "template.unknown", input_path)

    assert payload["valid"] is False
    assert payload["errors"][0]["code"] == "OUTPUT_TEMPLATE_UNKNOWN"


def test_validate_output_rejects_duplicate_template_binding(forge_root, tmp_path):
    _write_contract_root(
        forge_root,
        bindings=[
            {"template_id": "template.default", "schema": "registry/schemas/output.schema.json"},
            {"template_id": "template.default", "schema": "registry/schemas/output.schema.json"},
        ],
    )
    input_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")

    payload = validate_template_output(forge_root, "template.default", input_path)

    assert payload["errors"][0]["code"] == "OUTPUT_TEMPLATE_DUPLICATE"


def test_validate_output_rejects_missing_or_escaping_schema_path(forge_root, tmp_path):
    input_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")

    _write_contract_root(forge_root, schema_path="registry/schemas/missing.schema.json")
    missing = validate_template_output(forge_root, "template.default", input_path)
    assert missing["errors"][0]["code"] == "OUTPUT_SCHEMA_MISSING"

    _write_contract_root(forge_root, schema_path="../outside.schema.json")
    escaping = validate_template_output(forge_root, "template.default", input_path)
    assert escaping["errors"][0]["code"] == "OUTPUT_SCHEMA_PATH_ESCAPE"


def test_validate_output_renders_text_and_rejects_noncanonical_template(forge_root, tmp_path):
    _write_contract_root(forge_root)
    input_path = tmp_path / "output.json"
    input_path.write_text(json.dumps({"result": "ok"}), encoding="utf-8")
    runner = CliRunner()

    success = runner.invoke(
        cli,
        ["--root", str(forge_root), "validate-output", "--template", "template.default", "--input", str(input_path)],
    )
    assert success.exit_code == 0
    assert "Output contract: VALID" in success.output

    invalid = runner.invoke(
        cli,
        ["--root", str(forge_root), "validate-output", "--template", "default", "--input", str(input_path)],
    )
    assert invalid.exit_code != 0
    assert "canonical template.* id" in invalid.output


def test_validate_output_real_registry_smoke(tmp_path):
    forge_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "default-output.json"
    input_path.write_text(json.dumps({"result": "validated"}), encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["--root", str(forge_root), "--format", "json", "validate-output", "--template", "template.default", "--input", str(input_path)],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["valid"] is True
