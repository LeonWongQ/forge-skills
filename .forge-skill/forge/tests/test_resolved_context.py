# -*- coding: utf-8 -*-
"""Tests for read-only resolved context manifests."""

import json
from pathlib import Path

from click.testing import CliRunner

from forge_cli.cli import _execute_route, cli
from forge_cli.resolved_context import build_context_from_route


REAL_FORGE_ROOT = Path(__file__).resolve().parents[1]


def test_route_context_preserves_effective_selection():
    route = _execute_route(REAL_FORGE_ROOT, "帮我 review 一个 spring service 改动")
    manifest = build_context_from_route(REAL_FORGE_ROOT, route)

    assert manifest["resolution"]["ok"] is True
    assert manifest["selection"]["skill"] == route["skill"]["id"]
    assert manifest["selection"]["pack"] == route["pack"]["id"]
    assert any(item["id"] == "domain.spring" for item in manifest["context"]["domains"])
    assert all(not str(item.get("resolved_path")).startswith(str(REAL_FORGE_ROOT)) for items in manifest["context"].values() for item in items)


def test_resolve_cli_outputs_versioned_json_manifest():
    result = CliRunner().invoke(
        cli,
        ["--root", str(REAL_FORGE_ROOT), "--format", "json", "resolve", "帮我 review 一个 spring service 改动"],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(result.output)
    assert manifest["schema_version"] == "1.0"
    assert manifest["source"]["kind"] == "route"
    assert manifest["resolution"]["ok"] is True


def test_resolve_cli_reports_unmatched_context():
    result = CliRunner().invoke(
        cli,
        ["--root", str(REAL_FORGE_ROOT), "--format", "json", "resolve", "xyzzy nothing matches"],
    )

    assert result.exit_code != 0
    manifest = json.loads(result.output)
    assert manifest["selection"]["matched"] is False
    assert manifest["resolution"]["errors"][0]["code"] == "CONTEXT_SELECTION_UNMATCHED"


def test_resolve_cli_supports_explicit_composition():
    result = CliRunner().invoke(
        cli,
        ["--root", str(REAL_FORGE_ROOT), "--format", "json", "resolve", "--skill", "code-review", "--domain", "domain.spring"],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(result.output)
    assert manifest["source"]["kind"] == "compose"
    assert manifest["selection"]["skill"] == "skill.code_review"
    assert any(item["id"] == "domain.spring" for item in manifest["context"]["domains"])
