# -*- coding: utf-8 -*-
"""Tests for portable skill-evaluation baseline freezing."""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "freeze-skill-eval-baseline.py"
SPEC = importlib.util.spec_from_file_location("freeze_skill_eval_baseline", SCRIPT_PATH)
freeze_baseline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(freeze_baseline)
CORPUS = json.loads(freeze_baseline.CORPUS_PATH.read_text(encoding="utf-8"))


def _package(tmp_path: Path, pending: bool = True) -> tuple[Path, dict]:
    case = CORPUS["cases"][0]
    package = tmp_path / "package"
    response = package / case["id"] / "response.md"
    response.parent.mkdir(parents=True)
    response.write_text("response evidence\n", encoding="utf-8")
    (package / "run.json").write_text(json.dumps({
        "candidate": {"label": "source"},
        "results": [{
            "case_id": case["id"],
            "status": "completed_unscored",
            "duration_ms": 1000,
            "response_path": str(response),
        }],
    }), encoding="utf-8")
    value = None if pending else True
    forbidden = None if pending else False
    (package / "decisions.json").write_text(json.dumps({"scores": [{
        "case_id": case["id"],
        "hard_requirements": [value] * len(case["hard_requirements"]),
        "forbidden_behaviors": [forbidden] * len(case["forbidden_behaviors"]),
    }]}), encoding="utf-8")
    return package, case


def test_freeze_copies_response_and_records_pending_quality(tmp_path):
    package, case = _package(tmp_path)
    output = tmp_path / "baseline"

    manifest = freeze_baseline.freeze(package, output, "baseline-v1")

    frozen_run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert manifest["quality_status"] == "pending_human_review"
    assert manifest["pending_decision_count"] > 0
    assert frozen_run["candidate"]["role"] == "baseline"
    assert (output / frozen_run["results"][0]["response_path"]).read_text(encoding="utf-8") == "response evidence\n"
    response_key = f"responses/{case['id']}.md"
    assert response_key in manifest["artifact_hashes"]
    assert manifest["artifact_hashes"][response_key] == freeze_baseline.sha256(output / response_key)


def test_freeze_marks_complete_boolean_decisions_scored(tmp_path):
    package, _ = _package(tmp_path, pending=False)

    manifest = freeze_baseline.freeze(package, tmp_path / "baseline", "baseline-v1")

    assert manifest["quality_status"] == "scored"
    assert manifest["pending_decision_count"] == 0
    scored = json.loads((tmp_path / "baseline" / "scored.json").read_text(encoding="utf-8"))
    assert scored["results"][0]["gate"] == "pass"
    assert "scored.json" in manifest["artifact_hashes"]


def test_freeze_materializes_scored_failure_without_rejecting_baseline(tmp_path):
    package, case = _package(tmp_path, pending=False)
    decisions_path = package / "decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    decisions["scores"][0]["hard_requirements"][0] = False
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")

    manifest = freeze_baseline.freeze(package, tmp_path / "baseline", "baseline-v1")

    scored = json.loads((tmp_path / "baseline" / "scored.json").read_text(encoding="utf-8"))
    assert manifest["quality_status"] == "scored"
    assert scored["results"][0]["gate"] == "fail"
    assert case["hard_requirements"][0] in scored["results"][0]["failed_requirements"]


def test_freeze_rejects_noncompleted_evidence(tmp_path):
    package, _ = _package(tmp_path)
    run_path = package / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["results"][0]["status"] = "timeout"
    run_path.write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(ValueError, match="only completed_unscored"):
        freeze_baseline.freeze(package, tmp_path / "baseline", "baseline-v1")
