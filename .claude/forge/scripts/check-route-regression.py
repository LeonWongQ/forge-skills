#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge_cli.route_regression import evaluate_regression_case, load_regression_cases, summarize_regression_results
FORGE_CLI = [sys.executable, "-m", "forge_cli"]


def run_forge(mode: str, user_input: str, preferred_skill: Optional[str] = None) -> Dict[str, Any]:
    cmd = FORGE_CLI + [
        "--root",
        str(ROOT),
        "--format",
        "json",
        mode,
    ]
    if preferred_skill:
        cmd.extend(["--prefer", preferred_skill])
    cmd.append(user_input)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"forge command failed unexpectedly: mode={mode}, input={user_input}, "
            f"returncode={proc.returncode}, stderr={stderr}"
        )
    if not stdout:
        raise RuntimeError(
            f"forge command returned empty stdout: mode={mode}, input={user_input}, stderr={stderr}"
        )

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"forge command returned invalid JSON: mode={mode}, input={user_input}, "
            f"error={error}, stdout={stdout}"
        ) from error


def validate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    result = run_forge(case.get("mode"), case.get("input"), case.get("preferred_skill"))
    return evaluate_regression_case(case, result)


def main() -> int:
    try:
        cases = load_regression_cases(ROOT)
    except Exception as error:
        print(f"[ERROR] {error}")
        return 2

    passed = 0
    failed = 0
    print("Route / Recommend Regression")
    print(f"Cases: {len(cases)}")
    print("")

    evaluations = []
    for case in cases:
        try:
            result = validate_case(case)
        except Exception as error:
            result = {
                "id": case.get("id", "<unknown>") if isinstance(case, dict) else "<unknown>",
                "passed": False,
                "errors": [f"runner exception: {error}"],
                "actual": {},
            }

        evaluations.append(result)
        if result["passed"]:
            passed += 1
            print(f"[PASS] {result['id']}")
        else:
            failed += 1
            print(f"[FAIL] {result['id']}")
            print(f"  Input: {result.get('input')}")
            actual = result.get("actual", {})
            print(
                "  Actual: "
                f"skill={actual.get('skill')}, pack={actual.get('pack')}, "
                f"confidence={actual.get('confidence')}"
            )
            for error in result["errors"]:
                print(f"  - {error}")

    print("")
    summary = summarize_regression_results(evaluations)
    print(f"Summary: passed={passed}, failed={failed}, total={len(cases)}")
    print(f"By mode: {summary['by_mode']}")
    print(f"By category: {summary['by_category']}")
    print(f"Confidence distribution: {summary['confidence_distribution']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
