#!/usr/bin/env python3
"""Consolidate completed skill-evaluation runs into a human review package."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = FORGE_ROOT / "evals" / "skill-behavior-cases.json"


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_response(run_path: Path, result: dict) -> Path:
    local_path = run_path.parent / result["case_id"] / "response.md"
    if local_path.is_file():
        return local_path
    recorded = Path(result.get("response_path", ""))
    if recorded.is_file():
        return recorded
    raise ValueError(f"{result['case_id']}: response.md is missing beside {run_path}")


def collect_runs(run_paths: list[Path], corpus: dict) -> tuple[list[dict], list[dict], list[str]]:
    cases = {case["id"]: case for case in corpus["cases"]}
    selected = {}
    attempts = {case_id: [] for case_id in cases}
    sources = []
    corpus_hashes = set()
    for run_path in run_paths:
        run = load_json(run_path)
        candidate = run.get("candidate", {})
        results = run.get("results")
        if not isinstance(results, list) or not results:
            raise ValueError(f"{run_path}: results must be a non-empty array")
        source_case_ids = []
        source_results = []
        source_seen = set()
        for result in results:
            case_id = result.get("case_id")
            if case_id not in cases:
                raise ValueError(f"{run_path}: unknown case {case_id}")
            if case_id in source_seen:
                raise ValueError(f"{run_path}: duplicate result for {case_id}")
            source_seen.add(case_id)
            status = result.get("status")
            attempts[case_id].append({
                "run_path": str(run_path.resolve()),
                "status": status,
                "duration_ms": result.get("duration_ms", 0),
                "timeout_seconds": result.get("timeout_seconds"),
                "timeout_multiplier": result.get("timeout_multiplier", candidate.get("timeout_multiplier", 1.0)),
            })
            source_case_ids.append(case_id)
            source_results.append({"case_id": case_id, "status": status})
            if status != "completed_unscored":
                continue
            response_path = resolve_response(run_path, result)
            response = response_path.read_text(encoding="utf-8").strip()
            if not response:
                raise ValueError(f"{case_id}: response is empty")
            previous = selected.get(case_id)
            identity = (candidate.get("backend"), candidate.get("model"), candidate.get("user_config"))
            if previous and previous["candidate_identity"] != identity:
                raise ValueError(f"{case_id}: completed retries use different backend, model, or user configuration")
            selected[case_id] = {
                "case": cases[case_id],
                "result": result,
                "response": response,
                "response_path": response_path.resolve(),
                "response_sha256": file_sha256(response_path),
                "run_path": run_path.resolve(),
                "candidate": candidate,
                "candidate_identity": identity,
            }
        source_hash = run.get("corpus_sha256")
        if isinstance(source_hash, str):
            corpus_hashes.add(source_hash)
        sources.append({
            "run_path": str(run_path.resolve()),
            "run_sha256": file_sha256(run_path),
            "candidate": candidate,
            "case_ids": source_case_ids,
            "results": source_results,
            "recorded_corpus_sha256": source_hash,
        })
    collected = []
    for case in corpus["cases"]:
        item = selected.get(case["id"])
        if item:
            item["attempts"] = attempts[case["id"]]
            collected.append(item)
    return collected, sources, sorted(corpus_hashes)


def decisions_template(collected: list[dict]) -> dict:
    return {
        "evaluator": {
            "type": "human",
            "name": "",
            "version": "",
            "instructions": "For hard_requirements, true means satisfied. For forbidden_behaviors, true means observed.",
        },
        "scores": [
            {
                "case_id": item["case"]["id"],
                "rubric": {
                    "hard_requirements": item["case"]["hard_requirements"],
                    "forbidden_behaviors": item["case"]["forbidden_behaviors"],
                },
                "hard_requirements": [None] * len(item["case"]["hard_requirements"]),
                "forbidden_behaviors": [None] * len(item["case"]["forbidden_behaviors"]),
                "notes": "",
            }
            for item in collected
        ],
    }


def review_markdown(collected: list[dict], corpus_hashes: list[str], current_hash: str) -> str:
    total_ms = sum(item["result"].get("duration_ms", 0) for item in collected)
    total_attempts = sum(len(item["attempts"]) for item in collected)
    recovered_retries = sum(
        any(attempt["status"] != "completed_unscored" for attempt in item["attempts"])
        for item in collected
    )
    lines = [
        "# Skill Evaluation Human Review",
        "",
        "Review each response against every rubric item. Do not infer success from fluency or intent.",
        "",
        "- Hard requirement: check it only when the response satisfies it.",
        "- Forbidden behavior: check it only when the response exhibits it.",
        "- Transfer the final decisions to `decisions.json`; leave uncertain items as `null` until resolved.",
        "",
        "## Evidence Summary",
        "",
        f"- Completed responses: {len(collected)}",
        f"- Recorded attempts: {total_attempts}",
        f"- Cases recovered by retry: {recovered_retries}",
        f"- Total model duration: {total_ms / 1000:.3f} seconds",
        f"- Current corpus SHA-256: `{current_hash}`",
        f"- Recorded run corpus SHA-256: `{', '.join(corpus_hashes)}`",
    ]
    if corpus_hashes != [current_hash]:
        lines.extend([
            "- Corpus hash note: the current corpus adds execution capability metadata; review uses the current unchanged prompts and rubrics.",
        ])
    for index, item in enumerate(collected, start=1):
        case = item["case"]
        result = item["result"]
        lines.extend([
            "",
            f"## {index}. `{case['id']}`",
            "",
            f"Skill: `{case['skill']}`  ",
            f"Category: `{case['category']}`  ",
            f"Duration: {result.get('duration_ms', 0) / 1000:.3f} seconds  ",
            f"Attempts: {len(item['attempts'])}  ",
            f"Response SHA-256: `{item['response_sha256']}`",
            "",
            "### User Prompt",
            "",
            case["prompt"],
            "",
            "### Response",
            "",
            item["response"],
            "",
            "### Hard Requirements",
            "",
        ])
        lines.extend(f"- [ ] H{number}: {text}" for number, text in enumerate(case["hard_requirements"], start=1))
        lines.extend(["", "### Forbidden Behaviors", ""])
        lines.extend(f"- [ ] F{number}: {text}" for number, text in enumerate(case["forbidden_behaviors"], start=1))
        lines.extend(["", "### Reviewer Notes", "", "Decision: `pending`", "", "Notes:"])
    return "\n".join(lines) + "\n"


def consolidated_run(collected: list[dict], sources: list[dict], current_hash: str) -> dict:
    source_candidate = collected[0]["candidate"]
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "label": "consolidated-human-review",
            "backend": source_candidate.get("backend"),
            "model": source_candidate.get("model"),
            "user_config": source_candidate.get("user_config"),
            "source": "consolidated_existing_runs",
        },
        "corpus": str(CORPUS_PATH),
        "corpus_sha256": current_hash,
        "sources": sources,
        "results": [
            dict(
                item["result"],
                response_path=str(item["response_path"]),
                attempt_history=item["attempts"],
            )
            for item in collected
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=Path, help="Completed run.json; repeatable.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty review-package directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output.resolve(strict=False)
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"error: output directory is not empty: {output}")
    corpus = load_json(CORPUS_PATH)
    try:
        collected, sources, corpus_hashes = collect_runs(args.run, corpus)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"error: {error}") from None
    if not collected:
        raise SystemExit("error: no completed_unscored responses were found in the supplied runs")
    output.mkdir(parents=True, exist_ok=True)
    current_hash = file_sha256(CORPUS_PATH)
    (output / "review.md").write_text(review_markdown(collected, corpus_hashes, current_hash), encoding="utf-8")
    decisions = decisions_template(collected)
    (output / "decisions.template.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "decisions.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    run = consolidated_run(collected, sources, current_hash)
    (output / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared human review for {len(collected)} completed case(s) in {output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
