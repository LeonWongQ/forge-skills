# -*- coding: utf-8 -*-
"""Tests for derived module registry identities and explicit synchronization."""

import json
from pathlib import Path

from click.testing import CliRunner

from forge_cli.cli import cli
from forge_cli.registry_generation import derived_registry_issues


REAL_FORGE_ROOT = Path(__file__).resolve().parents[1]


def test_real_registry_is_synchronized():
    assert derived_registry_issues(REAL_FORGE_ROOT) == []


def test_derived_registry_reports_identity_drift(tmp_path):
    root = tmp_path / "forge"
    registry = root / "registry"
    registry.mkdir(parents=True)
    (registry / "modules.json").write_text(json.dumps({"layers": {"behaviors": [{"id": "behavior.review", "path": "wrong.md", "name": "Review", "role": "overlay"}], "domains": [], "templates": [], "checklists": [], "reports": []}}), encoding="utf-8")
    for name, key, payload in (
        ("behaviors.json", "behaviors", [{"id": "behavior.review", "path": "behaviors/review.md", "name": "Review"}]),
        ("domains.json", "domains", []),
        ("templates.json", "templates", []),
        ("checklists.json", "checklists", []),
        ("reports.json", "reports", []),
    ):
        (registry / name).write_text(json.dumps({key: payload}), encoding="utf-8")

    issues = derived_registry_issues(root)

    assert any(issue["code"] == "DERIVED_REGISTRY_IDENTITY_MISMATCH" and issue["field"] == "path" for issue in issues)


def test_registry_sync_check_cli_uses_real_registry():
    result = CliRunner().invoke(cli, ["--root", str(REAL_FORGE_ROOT), "registry-sync", "--check"])

    assert result.exit_code == 0
    assert "Registry sync: OK" in result.output
