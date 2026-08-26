# -*- coding: utf-8 -*-
"""Tests for the skill behavior evaluation corpus validator."""

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check-skill-eval-corpus.py"
SPEC = importlib.util.spec_from_file_location("check_skill_eval_corpus", SCRIPT_PATH)
check_skill_eval_corpus = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_skill_eval_corpus)


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    (root / "sample").mkdir(parents=True)
    (root / "sample" / "SKILL.md").write_text("# Sample\n", encoding="utf-8")
    return root


def _case(case_id: str, category: str) -> dict:
    return {
        "id": case_id,
        "skill": "sample",
        "category": category,
        "execution": {"fixture": "empty", "sandbox": "read-only", "timeout_seconds": 60, "mode": "automated", "requires_capabilities": ["filesystem_read"]},
        "prompt": "Handle this representative task.",
        "hard_requirements": ["Preserve the contract.", "Report verification evidence."],
        "forbidden_behaviors": ["Claim success without evidence."],
    }


def _write_corpus(path: Path, cases: list[dict]) -> None:
    path.write_text(json.dumps({"version": 1, "cases": cases}), encoding="utf-8")


def test_repository_corpus_is_valid():
    assert check_skill_eval_corpus.validate_corpus() == []


def test_repository_corpus_covers_ten_core_skills_and_expansion_cases():
    payload = json.loads(
        check_skill_eval_corpus.CORPUS_PATH.read_text(encoding="utf-8")
    )
    cases = {case["id"]: case for case in payload["cases"]}
    expected_expansion = {
        "skill-eval.security-review.sql-injection": "security-review",
        "skill-eval.release-readiness.tests-only": "release-readiness",
        "skill-eval.contract-compatibility.required-field": "contract-compatibility",
        "skill-eval.migration.big-bang-request": "migration",
        "skill-eval.test-implementation.boundaries": "test-implementation",
        "skill-eval.dependency-audit.offline-evidence": "dependency-audit",
    }

    assert len({case["skill"] for case in cases.values()}) >= 10
    assert {
        case_id: cases[case_id]["skill"] for case_id in expected_expansion
    } == expected_expansion
    assert check_skill_eval_corpus.REQUIRED_RISK_SKILLS <= {
        case["skill"] for case in cases.values()
    }


def test_corpus_requires_all_behavior_categories(tmp_path):
    corpus = tmp_path / "corpus.json"
    _write_corpus(corpus, [_case("skill-eval.sample.basic", "representative")])

    errors = check_skill_eval_corpus.validate_corpus(corpus, _skills_root(tmp_path))

    assert any("corpus is missing categories" in error for error in errors)


def test_corpus_rejects_duplicate_ids_and_unknown_skills(tmp_path):
    corpus = tmp_path / "corpus.json"
    cases = [
        _case("skill-eval.sample.same", "representative"),
        _case("skill-eval.sample.same", "boundary"),
        _case("skill-eval.sample.known", "known_failure"),
        _case("skill-eval.sample.adversarial", "adversarial"),
    ]
    cases[-1]["skill"] = "missing"
    _write_corpus(corpus, cases)

    errors = check_skill_eval_corpus.validate_corpus(corpus, _skills_root(tmp_path))

    assert "duplicate case id: skill-eval.sample.same" in errors
    assert any("must reference an existing skill" in error for error in errors)


def test_corpus_rejects_missing_and_unknown_capabilities(tmp_path):
    corpus = tmp_path / "corpus.json"
    cases = [
        _case("skill-eval.sample.representative", "representative"),
        _case("skill-eval.sample.boundary", "boundary"),
        _case("skill-eval.sample.known", "known_failure"),
        _case("skill-eval.sample.adversarial", "adversarial"),
    ]
    del cases[0]["execution"]["requires_capabilities"]
    cases[1]["execution"]["requires_capabilities"] = ["telepathy"]
    _write_corpus(corpus, cases)

    errors = check_skill_eval_corpus.validate_corpus(corpus, _skills_root(tmp_path))

    assert any("must contain at least one string" in error for error in errors)
    assert any("unsupported values: telepathy" in error for error in errors)
