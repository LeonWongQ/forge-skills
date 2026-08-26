# -*- coding: utf-8 -*-
"""Tests for deterministic semantic registry/composition validation."""

import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from forge_cli.cli import cli
from forge_cli.semantic_validation import validate_semantics


def _real_forge_copy(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "forge"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "out"))
    return target


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_real_registry_has_no_semantic_issues():
    root = Path(__file__).resolve().parents[1]
    assert validate_semantics(root) == []


def test_semantic_validation_detects_unknown_secondary_behavior(tmp_path):
    root = _real_forge_copy(tmp_path)
    path = root / "registry" / "compositions.json"
    data = _load(path)
    data["compositions"][0]["secondary_behaviors"] = ["behavior.unknown"]
    _write(path, data)

    issues = validate_semantics(root)

    assert any(issue["code"] == "SEMANTIC_SECONDARY_BEHAVIOR_UNKNOWN" for issue in issues)


def test_semantic_validation_detects_workflow_and_pack_module_issues(tmp_path):
    root = _real_forge_copy(tmp_path)
    workflow_path = root / "registry" / "workflows.json"
    workflows = _load(workflow_path)
    workflows["workflows"][0]["stages"] = ["engine.delivery", "engine.discover", "engine.delivery"]
    _write(workflow_path, workflows)

    pack_path = root / "packs" / "spring-review.json"
    pack = _load(pack_path)
    pack["modules"]["domains"].append("domain.unknown")
    _write(pack_path, pack)

    codes = {issue["code"] for issue in validate_semantics(root)}

    assert "SEMANTIC_WORKFLOW_STAGE_DUPLICATE" in codes
    assert "SEMANTIC_WORKFLOW_START_INVALID" in codes
    assert "SEMANTIC_WORKFLOW_DELIVERY_INVALID" in codes
    assert "SEMANTIC_WORKFLOW_ORDER_INVALID" in codes
    assert "SEMANTIC_PACK_MODULE_UNKNOWN" in codes


def test_semantic_validation_detects_template_binding_and_routing_references(tmp_path):
    root = _real_forge_copy(tmp_path)
    bindings_path = root / "registry" / "template-outputs.json"
    bindings = _load(bindings_path)
    bindings["template_outputs"].pop()
    _write(bindings_path, bindings)

    routing_path = root / "registry" / "skill-routing.json"
    routing = _load(routing_path)
    routing["tie_break_rules"].append({
        "skills": ["skill.code_review", "skill.unknown"],
        "prefer_if_set_present": "unknown_keywords",
    })
    _write(routing_path, routing)

    issues = validate_semantics(root)
    codes = {issue["code"] for issue in issues}

    assert "SEMANTIC_TEMPLATE_OUTPUT_COVERAGE" in codes
    assert "SEMANTIC_TIE_BREAK_INVALID" in codes
    assert "SEMANTIC_ROUTING_KEYWORD_SET_UNKNOWN" in codes
    assert issues == sorted(issues, key=lambda item: (item["code"], item["message"]))



def test_semantic_validation_detects_contract_fixture_invariants(tmp_path):
    root = _real_forge_copy(tmp_path)
    path = root / "registry" / "contracts.json"
    data = _load(path)
    data["contracts"][0]["baseline_schema"] = data["contracts"][0]["current_schema"]
    data["contracts"][0]["fixtures"]["current_valid"] = data["contracts"][0]["fixtures"]["baseline_valid"]
    _write(path, data)

    codes = {issue["code"] for issue in validate_semantics(root)}

    assert "SEMANTIC_CONTRACT_SCHEMA_BASELINE_EQUAL" in codes
    assert "SEMANTIC_CONTRACT_FIXTURE_GROUP_OVERLAP" in codes


def test_semantic_validation_detects_bias_rule_and_policy_issues(tmp_path):
    root = _real_forge_copy(tmp_path)
    path = root / "registry" / "skill-routing.json"
    routing = _load(path)
    skill_id = next(iter(routing["skill_bias_rules"]))
    routing["skill_bias_rules"][skill_id]["keyword_bonus"] = [{
        "keyword_set": "unknown_bonus",
        "weight": 1,
        "evidence_type": "test",
    }]
    routing["skill_bias_rules"][skill_id]["keyword_penalty"] = [{
        "keyword_set": "unknown_penalty",
        "weight": 1,
        "evidence_type": "test",
    }]
    routing["skill_bias_rules"][skill_id]["keyword_penalty_when_trigger_matched"] = [{
        "keyword_set": "unknown_trigger_penalty",
        "weight": 1,
        "evidence_type": "test",
    }]
    routing["skill_bias_rules"][skill_id]["keyword_penalty_when_absent"] = [{
        "required_set": "unknown_required",
        "keyword_set": "unknown_absent",
        "weight": 1,
        "evidence_type": "test",
    }]
    routing["skill_bias_rules"][skill_id]["postmortem_hint_bonus"] = {
        "requires_keyword_set": "unknown_postmortem",
        "text_any": ["hint"],
        "weight": 1,
        "evidence_type": "test",
    }
    routing["generic_trigger_penalties"]["skill.unknown"] = ["generic"]
    routing["confidence_policy"]["ordinary_gap_low_max"] = 6
    routing["confidence_policy"]["ordinary_gap_medium_max"] = 5
    _write(path, routing)

    issues = validate_semantics(root)
    keyword_set_issues = [issue for issue in issues if issue["code"] == "SEMANTIC_ROUTING_KEYWORD_SET_UNKNOWN"]
    fields = {issue["details"].get("field") for issue in keyword_set_issues}

    assert {"keyword_set", "required_set", "requires_keyword_set"} <= fields
    assert any(issue["code"] == "SEMANTIC_ROUTING_SKILL_UNKNOWN" for issue in issues)
    assert any(issue["code"] == "SEMANTIC_CONFIDENCE_POLICY_GAP_ORDER_INVALID" for issue in issues)


def test_cli_semantics_check_reports_success_and_failure(tmp_path):
    root = _real_forge_copy(tmp_path)
    runner = CliRunner()

    success = runner.invoke(cli, ["--root", str(root), "--format", "json", "validate", "--check", "semantics"])
    assert success.exit_code == 0
    assert json.loads(success.output)["checks"][0]["name"] == "semantics"

    workflows_path = root / "registry" / "workflows.json"
    workflows = _load(workflows_path)
    workflows["default_workflow"] = "workflow.unknown"
    _write(workflows_path, workflows)

    failure = runner.invoke(cli, ["--root", str(root), "--format", "json", "validate", "--check", "semantics"])
    payload = json.loads(failure.output)
    assert failure.exit_code != 0
    assert any(message["code"] == "SEMANTIC_DEFAULT_WORKFLOW_UNKNOWN" for message in payload["checks"][0]["messages"])
