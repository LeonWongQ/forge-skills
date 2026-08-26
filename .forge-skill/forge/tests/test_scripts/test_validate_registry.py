# -*- coding: utf-8 -*-
"""Regression tests for the standalone registry schema validator."""

import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

from forge_cli.constants import REGISTRY_SCHEMA_CANDIDATES


FORGE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = FORGE_ROOT / "scripts" / "validate-registry.py"


def _copy_root(tmp_path: Path) -> Path:
    target = tmp_path / "forge"
    shutil.copytree(FORGE_ROOT, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "out"))
    return target


def _run_validator(root: Path):
    return subprocess.run(
        [sys.executable, "validate-registry.py"],
        cwd=root / "scripts",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_standalone_schema_map_matches_cli_registry_mapping():
    namespace = runpy.run_path(str(SCRIPT_PATH))
    schema_map = namespace["REGISTRY_SCHEMA_MAP"]

    assert set(schema_map) == set(REGISTRY_SCHEMA_CANDIDATES)
    assert schema_map["contracts.json"].name == "contracts.schema.json"


def test_standalone_validator_validates_contract_catalog_from_scripts_directory():
    result = _run_validator(FORGE_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "contracts.json passes schema validation" in result.stdout


def test_standalone_validator_rejects_json_valid_invalid_contract_catalog(tmp_path):
    root = _copy_root(tmp_path)
    catalog_path = root / "registry" / "contracts.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"][0]["kind"] = "rpc"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    result = _run_validator(root)

    assert result.returncode == 1
    assert "contracts.json: schema violation" in result.stdout
