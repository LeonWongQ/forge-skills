# -*- coding: utf-8 -*-
"""Tests for explicit skill evaluation rubric scoring."""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "score-skill-evals.py"
SPEC = importlib.util.spec_from_file_location("score_skill_evals", SCRIPT_PATH)
score_skill_evals = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(score_skill_evals)
CORPUS = json.loads((Path(__file__).resolve().parents[2] / "evals" / "skill-behavior-cases.json").read_text(encoding="utf-8"))


def _run(case_id: str, status: str = "completed_unscored") -> dict:
    return {"results": [{"case_id": case_id, "status": status}]}


def test_all_satisfied_rubrics_pass():
    case = CORPUS["cases"][0]
    decisions = {"scores": [{
        "case_id": case["id"],
        "hard_requirements": [True] * len(case["hard_requirements"]),
        "forbidden_behaviors": [False] * len(case["forbidden_behaviors"]),
    }]}

    scored = score_skill_evals.score_run(_run(case["id"]), decisions, CORPUS)

    assert scored["results"][0]["gate"] == "pass"
    assert scored["gate_summary"] == {"passed": 1, "failed": 0, "unscored": 0, "excluded": 0, "ok": True}


def test_timeout_fails_even_when_rubric_is_satisfied():
    case = CORPUS["cases"][0]
    decisions = {"scores": [{
        "case_id": case["id"],
        "hard_requirements": [True] * len(case["hard_requirements"]),
        "forbidden_behaviors": [False] * len(case["forbidden_behaviors"]),
    }]}

    scored = score_skill_evals.score_run(_run(case["id"], "timeout"), decisions, CORPUS)

    assert scored["results"][0]["gate"] == "fail"


@pytest.mark.parametrize("status", ["unsupported_backend", "environment_gated_not_run"])
def test_nonapplicable_results_are_excluded_from_success_gate(status):
    runnable = CORPUS["cases"][0]
    excluded = CORPUS["cases"][4]
    run = {"results": [
        {"case_id": runnable["id"], "status": "completed_unscored"},
        {"case_id": excluded["id"], "status": status},
    ]}
    decisions = {"scores": [{
        "case_id": runnable["id"],
        "hard_requirements": [True] * len(runnable["hard_requirements"]),
        "forbidden_behaviors": [False] * len(runnable["forbidden_behaviors"]),
    }]}

    scored = score_skill_evals.score_run(run, decisions, CORPUS)

    assert scored["results"][1]["gate"] == "excluded"
    assert scored["gate_summary"] == {"passed": 1, "failed": 0, "unscored": 0, "excluded": 1, "ok": True}


def test_rubric_decisions_must_match_corpus_cardinality():
    case = CORPUS["cases"][0]
    decisions = {"scores": [{"case_id": case["id"], "hard_requirements": [True], "forbidden_behaviors": [False]}]}

    with pytest.raises(ValueError, match="must match the corpus rubric"):
        score_skill_evals.score_run(_run(case["id"]), decisions, CORPUS)


def test_main_reports_incomplete_decisions_without_traceback(tmp_path, capsys):
    case = CORPUS["cases"][0]
    run_path = tmp_path / "run.json"
    decisions_path = tmp_path / "decisions.json"
    run_path.write_text(json.dumps(_run(case["id"])), encoding="utf-8")
    decisions_path.write_text(json.dumps({"scores": [{
        "case_id": case["id"],
        "hard_requirements": [None] * len(case["hard_requirements"]),
        "forbidden_behaviors": [None] * len(case["forbidden_behaviors"]),
    }]}), encoding="utf-8")

    result = score_skill_evals.main([
        "--run", str(run_path),
        "--decisions", str(decisions_path),
        "--output", str(tmp_path / "scored.json"),
    ])

    captured = capsys.readouterr()
    assert result == 2
    assert "incomplete or invalid" in captured.err
    assert "Traceback" not in captured.err
