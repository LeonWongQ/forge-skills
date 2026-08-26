#!/usr/bin/env python3
"""Apply explicit rubric decisions to a skill evaluation run."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = FORGE_ROOT / "evals" / "skill-behavior-cases.json"
EXCLUDED_STATUSES = {"environment_gated_not_run", "unsupported_backend"}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def score_run(run: dict, decisions: dict, corpus: dict) -> dict:
    cases = {case["id"]: case for case in corpus["cases"]}
    decision_items = decisions.get("scores")
    if not isinstance(decision_items, list):
        raise ValueError("decisions.scores must be an array")
    by_case = {}
    for item in decision_items:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError("each score must contain a string case_id")
        if item["case_id"] in by_case:
            raise ValueError(f"duplicate score for {item['case_id']}")
        by_case[item["case_id"]] = item

    scored = deepcopy(run)
    passed = failed = unscored = excluded = 0
    for result in scored.get("results", []):
        case_id = result["case_id"]
        case = cases.get(case_id)
        if case is None:
            raise ValueError(f"run references unknown case: {case_id}")
        if result.get("status") in EXCLUDED_STATUSES:
            result["gate"] = "excluded"
            result["failed_requirements"] = []
            result["observed_forbidden_behaviors"] = []
            excluded += 1
            continue
        decision = by_case.get(case_id)
        if decision is None:
            result["gate"] = "unscored"
            result["failed_requirements"] = []
            unscored += 1
            continue
        hard = decision.get("hard_requirements")
        forbidden = decision.get("forbidden_behaviors")
        if not isinstance(hard, list) or len(hard) != len(case["hard_requirements"]) or not all(isinstance(value, bool) for value in hard):
            raise ValueError(f"{case_id}: hard_requirements decisions must match the corpus rubric")
        if not isinstance(forbidden, list) or len(forbidden) != len(case["forbidden_behaviors"]) or not all(isinstance(value, bool) for value in forbidden):
            raise ValueError(f"{case_id}: forbidden_behaviors decisions must match the corpus rubric")
        failed_requirements = [text for text, satisfied in zip(case["hard_requirements"], hard) if not satisfied]
        observed_forbidden = [text for text, observed in zip(case["forbidden_behaviors"], forbidden) if observed]
        execution_failed = result.get("status") != "completed_unscored"
        gate = "fail" if execution_failed or failed_requirements or observed_forbidden else "pass"
        result.update({
            "gate": gate,
            "failed_requirements": failed_requirements,
            "observed_forbidden_behaviors": observed_forbidden,
            "score_notes": decision.get("notes"),
        })
        if gate == "pass":
            passed += 1
        else:
            failed += 1
    scored["gate_summary"] = {
        "passed": passed,
        "failed": failed,
        "unscored": unscored,
        "excluded": excluded,
        "ok": failed == 0 and unscored == 0,
    }
    return scored


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        scored = score_run(load_json(args.run), load_json(args.decisions), load_json(CORPUS_PATH))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"error: evaluation decisions are incomplete or invalid: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = scored["gate_summary"]
    print(
        f"Skill eval gate: passed={summary['passed']}, failed={summary['failed']}, "
        f"unscored={summary['unscored']}, excluded={summary['excluded']}"
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
