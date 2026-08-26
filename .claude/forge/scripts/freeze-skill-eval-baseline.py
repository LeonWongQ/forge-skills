#!/usr/bin/env python3
"""Freeze a reviewed skill-evaluation package as a portable baseline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = FORGE_ROOT / "evals" / "skill-behavior-cases.json"


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_complete_run(run: dict, decisions: dict, corpus: dict) -> dict:
    scorer_path = Path(__file__).resolve().parent / "score-skill-evals.py"
    spec = importlib.util.spec_from_file_location("forge_score_skill_evals", scorer_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load skill evaluation scorer")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    return scorer.score_run(run, decisions, corpus)


def decision_status(decisions: dict, cases: dict[str, dict]) -> dict:
    pending = total = 0
    seen = set()
    for score in decisions.get("scores", []):
        case_id = score.get("case_id")
        if case_id not in cases or case_id in seen:
            raise ValueError(f"invalid or duplicate decision case: {case_id}")
        seen.add(case_id)
        case = cases[case_id]
        for key in ("hard_requirements", "forbidden_behaviors"):
            values = score.get(key)
            if not isinstance(values, list) or len(values) != len(case[key]):
                raise ValueError(f"{case_id}: {key} decisions must match the corpus rubric")
            if not all(value is None or isinstance(value, bool) for value in values):
                raise ValueError(f"{case_id}: {key} decisions must be Boolean or null")
            total += len(values)
            pending += sum(value is None for value in values)
    return {
        "status": "scored" if pending == 0 else "pending_human_review",
        "decision_count": total,
        "pending_decision_count": pending,
    }


def freeze(package: Path, output: Path, label: str) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    run_path = package / "run.json"
    decisions_path = package / "decisions.json"
    run = load_json(run_path)
    decisions = load_json(decisions_path)
    corpus = load_json(CORPUS_PATH)
    cases = {case["id"]: case for case in corpus["cases"]}
    results = run.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("run.results must be a non-empty array")
    case_ids = [result.get("case_id") for result in results]
    if len(case_ids) != len(set(case_ids)) or any(case_id not in cases for case_id in case_ids):
        raise ValueError("run must contain unique corpus case IDs")
    if any(result.get("status") != "completed_unscored" for result in results):
        raise ValueError("baseline evidence must contain only completed_unscored results")
    status = decision_status(decisions, cases)
    decision_ids = {score["case_id"] for score in decisions.get("scores", [])}
    if decision_ids != set(case_ids):
        raise ValueError("decision cases must exactly match run cases")

    output.mkdir(parents=True, exist_ok=True)
    responses = output / "responses"
    responses.mkdir()
    frozen_run = json.loads(json.dumps(run))
    artifact_hashes = {}
    for result in frozen_run["results"]:
        case_id = result["case_id"]
        source = package / case_id / "response.md"
        if not source.is_file():
            source = Path(result.get("response_path", ""))
        if not source.is_file():
            raise ValueError(f"{case_id}: response evidence is missing")
        destination = responses / f"{case_id}.md"
        shutil.copyfile(source, destination)
        result["source_response_path"] = result.get("response_path")
        result["response_path"] = f"responses/{destination.name}"
        artifact_hashes[result["response_path"]] = sha256(destination)

    frozen_run["candidate"] = dict(frozen_run.get("candidate", {}), label=label, role="baseline")
    frozen_run["corpus_sha256"] = sha256(CORPUS_PATH)
    frozen_run["corpus"] = str(CORPUS_PATH)
    (output / "run.json").write_text(json.dumps(frozen_run, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(decisions_path, output / "decisions.json")
    if (package / "review.md").is_file():
        shutil.copyfile(package / "review.md", output / "review.md")
    artifact_hashes.update({
        "run.json": sha256(output / "run.json"),
        "decisions.json": sha256(output / "decisions.json"),
    })
    if status["status"] == "scored":
        scored = score_complete_run(frozen_run, decisions, corpus)
        (output / "scored.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
        artifact_hashes["scored.json"] = sha256(output / "scored.json")
    manifest = {
        "schema_version": 1,
        "label": label,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": sha256(CORPUS_PATH),
        "case_ids": case_ids,
        "case_count": len(case_ids),
        "execution_status": "completed",
        "quality_status": status["status"],
        "decision_count": status["decision_count"],
        "pending_decision_count": status["pending_decision_count"],
        "total_duration_ms": sum(result.get("duration_ms", 0) for result in results),
        "source": {
            "package": str(package.resolve()),
            "run_sha256": sha256(run_path),
            "decisions_sha256": sha256(decisions_path),
        },
        "artifact_hashes": artifact_hashes,
    }
    (output / "baseline.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--label", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = freeze(args.package.resolve(), args.output.resolve(strict=False), args.label)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"error: {error}") from None
    print(
        f"Frozen baseline {manifest['label']}: cases={manifest['case_count']}, "
        f"quality={manifest['quality_status']}, pending={manifest['pending_decision_count']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
