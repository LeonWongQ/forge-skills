# -*- coding: utf-8 -*-
"""Tests for explicit registry-derived documentation fact markers."""

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check-documentation-facts.py"
SPEC = importlib.util.spec_from_file_location("check_documentation_facts", SCRIPT_PATH)
check_documentation_facts = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_documentation_facts)


def _write_json(path: Path, key: str, count: int) -> None:
    path.write_text(json.dumps({key: [{} for _ in range(count)]}), encoding="utf-8")


def _root_with_facts(tmp_path: Path) -> Path:
    root = tmp_path / "forge"
    registry = root / "registry"
    registry.mkdir(parents=True)
    _write_json(registry / "skills.json", "skills", 2)
    _write_json(registry / "packs.json", "packs", 3)
    _write_json(registry / "domains.json", "domains", 4)
    _write_json(registry / "checklists.json", "checklists", 5)
    _write_json(registry / "templates.json", "templates", 6)
    evals = root / "evals"
    evals.mkdir()
    (evals / "skill-behavior-cases.json").write_text(
        json.dumps({"cases": [{"skill": "alpha"}, {"skill": "alpha"}, {"skill": "beta"}]}),
        encoding="utf-8",
    )
    _write_json(registry / "route-regression.json", "cases", 7)
    (registry / "project.json").write_text('{"version": "1.2.0"}', encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nversion = '1.2.0'\n", encoding="utf-8")
    (root / "forge_cli").mkdir()
    (root / "forge_cli" / "constants.py").write_text(
        "ALL_CHECKS = ['registry', 'paths']\n", encoding="utf-8"
    )
    return root


def _marker() -> str:
    return (
        "<!-- forge-facts: skills=2 packs=3 domains=4 checklists=5 templates=6 "
        "validation-count=2 validation-checks=registry,paths version=1.2.0 "
        "route-regression-count=7 -->\n"
    )


def test_registry_facts_are_derived_from_registry_and_constants(tmp_path):
    root = _root_with_facts(tmp_path)

    assert check_documentation_facts.registry_facts(root) == {
        "skills": "2",
        "packs": "3",
        "domains": "4",
        "checklists": "5",
        "templates": "6",
        "validation-count": "2",
        "validation-checks": "registry,paths",
        "version": "1.2.0",
        "route-regression-count": "7",
        "skill-eval-case-count": "3",
        "skill-eval-skill-count": "2",
    }


def test_validation_accepts_matching_document_markers(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    rules = root.parent / "rules"
    rules.mkdir()
    (root / "README.md").write_text(_marker(), encoding="utf-8")
    (rules / "000-forge.mdc").write_text(_marker(), encoding="utf-8")
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {
        Path("README.md"): check_documentation_facts.FULL_FACT_KEYS,
        Path("../rules/000-forge.mdc"): check_documentation_facts.FULL_FACT_KEYS,
    })

    assert check_documentation_facts.validate_documentation_facts(root) == []


def test_validation_reports_outdated_or_missing_markers(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    rules = root.parent / "rules"
    rules.mkdir()
    (root / "README.md").write_text(_marker().replace("skills=2", "skills=22"), encoding="utf-8")
    (rules / "000-forge.mdc").write_text("# no facts\n", encoding="utf-8")
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {
        Path("README.md"): check_documentation_facts.FULL_FACT_KEYS,
        Path("../rules/000-forge.mdc"): check_documentation_facts.FULL_FACT_KEYS,
    })

    issues = check_documentation_facts.validate_documentation_facts(root)

    assert any("skills='22', expected '2'" in issue for issue in issues)
    assert any("missing <!-- forge-facts: ... --> marker" in issue for issue in issues)


def test_validation_reports_project_version_drift(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    (root / "registry" / "project.json").write_text('{"version": "1.1.1"}', encoding="utf-8")
    (root / "README.md").write_text(_marker(), encoding="utf-8")
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {Path("README.md"): check_documentation_facts.FULL_FACT_KEYS})

    issues = check_documentation_facts.validate_documentation_facts(root)

    assert "registry/project.json: version='1.1.1', package version='1.2.0'" in issues


def test_validation_reports_outdated_regression_count(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    (root / "README.md").write_text(
        _marker().replace("route-regression-count=7", "route-regression-count=39"),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {Path("README.md"): check_documentation_facts.FULL_FACT_KEYS})

    issues = check_documentation_facts.validate_documentation_facts(root)

    assert any("route-regression-count='39', expected '7'" in issue for issue in issues)


def test_validation_supports_documents_with_partial_fact_ownership(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    (root / "STATUS.md").write_text(
        "<!-- forge-facts: validation-count=2 route-regression-count=7 -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {
        Path("STATUS.md"): ("validation-count", "route-regression-count"),
    })

    assert check_documentation_facts.validate_documentation_facts(root) == []


def test_validation_reports_outdated_behavior_corpus_count(tmp_path, monkeypatch):
    root = _root_with_facts(tmp_path)
    (root / "scripts").mkdir()
    (root / "scripts" / "README.md").write_text(
        "<!-- forge-facts: skill-eval-case-count=14 skill-eval-skill-count=10 -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_documentation_facts, "DOCUMENTS", {
        Path("scripts/README.md"): ("skill-eval-case-count", "skill-eval-skill-count"),
    })

    issues = check_documentation_facts.validate_documentation_facts(root)

    assert any("skill-eval-case-count='14', expected '3'" in issue for issue in issues)
    assert any("skill-eval-skill-count='10', expected '2'" in issue for issue in issues)


def test_deployment_documents_match_link_contract():
    forge_root = Path(__file__).resolve().parents[1]
    cursor = (forge_root / "INTEGRATIONS" / "cursor.md").read_text(encoding="utf-8")
    bootstrap = (forge_root / "BOOTSTRAP.md").read_text(encoding="utf-8")

    assert ".cursor/skills/" in cursor
    assert ".cursor/rules/000-forge.mdc" in cursor
    assert "./agents/" not in cursor
    assert "install-link-forge.bat" in bootstrap
    assert "claude|cursor|codex" in bootstrap
    assert "Python 3.11+" in bootstrap
    assert "verifies the resulting junction targets" in bootstrap
    assert "deployment-verify" not in bootstrap
    assert "deployment-verify" not in cursor
    assert (forge_root / "INTEGRATIONS" / "codex.md").is_file()
