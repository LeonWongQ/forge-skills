"""Tests for retry-aware Skill evaluation review packaging."""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare-skill-eval-review.py"
SPEC = importlib.util.spec_from_file_location("prepare_skill_eval_review", SCRIPT_PATH)
prepare_review = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prepare_review)


CASE_ID = "skill-eval.alpha.retry"
CORPUS = {
    "cases": [{
        "id": CASE_ID,
        "skill": "alpha",
        "category": "representative",
        "prompt": "Evaluate alpha.",
        "hard_requirements": ["Return evidence."],
        "forbidden_behaviors": ["Invent evidence."],
    }],
}


def _write_run(root: Path, status: str, *, model: str = "model-a", response: str | None = None) -> Path:
    root.mkdir()
    result = {
        "case_id": CASE_ID,
        "status": status,
        "duration_ms": 100,
        "timeout_seconds": 60,
    }
    run = {
        "candidate": {"backend": "codex", "model": model, "user_config": "enabled"},
        "corpus_sha256": "corpus-hash",
        "results": [result],
    }
    run_path = root / "run.json"
    run_path.write_text(json.dumps(run), encoding="utf-8")
    if response is not None:
        response_path = root / CASE_ID / "response.md"
        response_path.parent.mkdir()
        response_path.write_text(response, encoding="utf-8")
    return run_path


def test_collect_runs_selects_successful_retry_and_preserves_attempts(tmp_path):
    initial = _write_run(tmp_path / "initial", "timeout")
    retry = _write_run(tmp_path / "retry", "completed_unscored", response="Evidence-backed response.")

    collected, sources, hashes = prepare_review.collect_runs([initial, retry], CORPUS)

    assert len(collected) == 1
    assert collected[0]["response"] == "Evidence-backed response."
    assert [attempt["status"] for attempt in collected[0]["attempts"]] == ["timeout", "completed_unscored"]
    assert sources[0]["case_ids"] == [CASE_ID]
    assert sources[0]["results"] == [{"case_id": CASE_ID, "status": "timeout"}]
    assert hashes == ["corpus-hash"]


def test_collect_runs_rejects_completed_retries_from_different_models(tmp_path):
    first = _write_run(tmp_path / "first", "completed_unscored", response="First response.")
    second = _write_run(
        tmp_path / "second",
        "completed_unscored",
        model="model-b",
        response="Second response.",
    )

    with pytest.raises(ValueError, match="different backend, model, or user configuration"):
        prepare_review.collect_runs([first, second], CORPUS)


def test_consolidated_run_uses_source_candidate_and_attempt_history(tmp_path):
    initial = _write_run(tmp_path / "initial", "runner_error")
    retry = _write_run(tmp_path / "retry", "completed_unscored", response="Recovered response.")
    collected, sources, _ = prepare_review.collect_runs([initial, retry], CORPUS)

    consolidated = prepare_review.consolidated_run(collected, sources, "current-hash")

    assert consolidated["candidate"]["backend"] == "codex"
    assert consolidated["candidate"]["model"] == "model-a"
    assert [attempt["status"] for attempt in consolidated["results"][0]["attempt_history"]] == [
        "runner_error",
        "completed_unscored",
    ]
