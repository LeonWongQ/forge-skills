# -*- coding: utf-8 -*-
"""Tests for consolidated human skill-evaluation review packages."""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "prepare-skill-eval-review.py"
SPEC = importlib.util.spec_from_file_location("prepare_skill_eval_review", SCRIPT_PATH)
prepare_review = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prepare_review)
CORPUS = json.loads(prepare_review.CORPUS_PATH.read_text(encoding="utf-8"))


def _source_run(tmp_path: Path, case: dict, name: str = "source") -> Path:
    root = tmp_path / name
    response = root / case["id"] / "response.md"
    response.parent.mkdir(parents=True)
    response.write_text("Evidence-based response.\n", encoding="utf-8")
    run_path = root / "run.json"
    run_path.write_text(json.dumps({
        "candidate": {"backend": "claude", "model": "test"},
        "corpus_sha256": "historical-hash",
        "results": [{
            "case_id": case["id"],
            "skill": case["skill"],
            "status": "completed_unscored",
            "duration_ms": 1234,
            "response_path": "stale/absolute/path.md",
        }],
    }), encoding="utf-8")
    return run_path


def test_main_builds_review_decisions_and_consolidated_run(tmp_path):
    case = CORPUS["cases"][0]
    source = _source_run(tmp_path, case)
    output = tmp_path / "review"

    assert prepare_review.main(["--run", str(source), "--output", str(output)]) == 0

    review = (output / "review.md").read_text(encoding="utf-8")
    decisions = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert case["prompt"] in review
    assert case["hard_requirements"][0] in review
    assert "Evidence-based response." in review
    assert decisions["scores"][0]["hard_requirements"] == [None] * len(case["hard_requirements"])
    assert decisions["scores"][0]["rubric"]["hard_requirements"] == case["hard_requirements"]
    assert Path(run["results"][0]["response_path"]).is_file()
    assert run["sources"][0]["recorded_corpus_sha256"] == "historical-hash"


def test_duplicate_case_across_runs_is_preserved_as_retry_history(tmp_path):
    case = CORPUS["cases"][0]
    first = _source_run(tmp_path, case, "first")
    second = _source_run(tmp_path, case, "second")
    output = tmp_path / "review"

    assert prepare_review.main(["--run", str(first), "--run", str(second), "--output", str(output)]) == 0

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert [attempt["status"] for attempt in run["results"][0]["attempt_history"]] == [
        "completed_unscored",
        "completed_unscored",
    ]


def test_run_without_completed_result_is_rejected(tmp_path):
    case = CORPUS["cases"][0]
    source = _source_run(tmp_path, case)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["results"][0]["status"] = "timeout"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit, match="no completed_unscored responses"):
        prepare_review.main(["--run", str(source), "--output", str(tmp_path / "review")])


def test_nonempty_output_is_rejected(tmp_path):
    case = CORPUS["cases"][0]
    source = _source_run(tmp_path, case)
    output = tmp_path / "review"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(SystemExit, match="not empty"):
        prepare_review.main(["--run", str(source), "--output", str(output)])
