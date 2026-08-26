# -*- coding: utf-8 -*-
"""Tests for fixed-case skill-evaluation comparisons."""

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare-skill-evals.py"
SPEC = importlib.util.spec_from_file_location("compare_skill_evals", SCRIPT_PATH)
compare_evals = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compare_evals)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _baseline(tmp_path: Path, gate: str | None = None) -> Path:
    root = tmp_path / "baseline"
    corpus_hash = "corpus-v1"
    result = {"case_id": "case.one", "status": "completed_unscored", "duration_ms": 1000}
    if gate:
        result["gate"] = gate
    run_name = "scored.json" if gate else "run.json"
    _write(root / run_name, {"corpus_sha256": corpus_hash, "results": [result]})
    run_hash = hashlib.sha256((root / run_name).read_bytes()).hexdigest()
    _write(root / "baseline.json", {
        "label": "baseline-v1",
        "case_ids": ["case.one"],
        "corpus_sha256": corpus_hash,
        "artifact_hashes": {run_name: run_hash},
    })
    return root


def _candidate(path: Path, results: list[dict], corpus_hash: str = "corpus-v1") -> None:
    _write(path, {"corpus_sha256": corpus_hash, "results": results})


def test_unscored_comparison_reports_latency_but_not_quality(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [{"case_id": "case.one", "status": "completed_unscored", "duration_ms": 800}])

    report = compare_evals.compare(baseline, candidate)

    assert report["quality"]["status"] == "unavailable_pending_human_scoring"
    assert report["gate_decision"] == "pending_human_scoring"
    assert report["latency"]["delta_ms"] == -200
    assert report["latency"]["delta_percent"] == -20.0


def test_execution_regression_is_separate_from_pending_quality(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [{"case_id": "case.one", "status": "timeout", "duration_ms": 2000}])

    report = compare_evals.compare(baseline, candidate)

    assert report["execution"]["regressions"] == ["case.one"]
    assert report["quality"]["ok"] is None
    assert report["gate_decision"] == "fail"


def test_scored_pass_to_fail_is_quality_regression(tmp_path):
    baseline = _baseline(tmp_path, gate="pass")
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [{
        "case_id": "case.one", "status": "completed_unscored", "duration_ms": 900, "gate": "fail"
    }])

    report = compare_evals.compare(baseline, candidate)

    assert report["quality"]["regressions"] == ["case.one"]
    assert report["gate_decision"] == "fail"


def test_candidate_must_have_exact_case_parity(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [])

    with pytest.raises(ValueError, match="candidate case mismatch"):
        compare_evals.compare(baseline, candidate)


def test_duplicate_candidate_case_is_rejected_before_collapsing(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = tmp_path / "candidate.json"
    result = {"case_id": "case.one", "status": "completed_unscored", "duration_ms": 1000}
    _candidate(candidate, [result, dict(result, status="timeout")])

    with pytest.raises(ValueError, match="duplicate case"):
        compare_evals.compare(baseline, candidate)


def test_tampered_baseline_artifact_is_rejected(tmp_path):
    baseline = _baseline(tmp_path)
    run_path = baseline / "run.json"
    run_path.write_text(run_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [{"case_id": "case.one", "status": "completed_unscored", "duration_ms": 1000}])

    with pytest.raises(ValueError, match="hash mismatch"):
        compare_evals.compare(baseline, candidate)


def test_candidate_corpus_must_match_frozen_baseline(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = tmp_path / "candidate.json"
    _candidate(candidate, [{"case_id": "case.one", "status": "completed_unscored", "duration_ms": 1000}], "corpus-v2")

    with pytest.raises(ValueError, match="candidate corpus"):
        compare_evals.compare(baseline, candidate)
