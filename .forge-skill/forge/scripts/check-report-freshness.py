#!/usr/bin/env python3
"""Compare committed Forge diagnostic reports against fresh report contracts."""

import json
import sys
from pathlib import Path
from typing import Any

FORGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FORGE_ROOT))

from forge_cli.constants import ALL_CHECKS, CHECK_PATHS, CHECK_REGISTRY, CHECK_REFS
from forge_cli.report_contract import canonical_report_contract, first_contract_difference


OUT_DIR = FORGE_ROOT / "out"
REPORT_NAMES = ("validate", "doctor")
EXPECTED_CHECK_NAMES = {
    "validate": ALL_CHECKS,
    "doctor": [CHECK_REGISTRY, CHECK_PATHS, CHECK_REFS],
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as report_file:
        return json.load(report_file)


def check_report(name: str) -> bool:
    committed_path = OUT_DIR / f"{name}-report.json"
    fresh_path = OUT_DIR / f"{name}-report.fresh.json"

    if not committed_path.exists():
        print(f"SKIP {name}-report.json: committed report not found at {committed_path}")
        return True
    if not fresh_path.exists():
        print(
            f"FAIL {name}-report.json: fresh report not found at {fresh_path} "
            "(upstream step failed or did not run)"
        )
        return False

    try:
        committed = canonical_report_contract(load_json(committed_path), expected_command=name)
        fresh = canonical_report_contract(load_json(fresh_path), expected_command=name)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"FAIL {name}-report.json: invalid report contract: {error}")
        return False

    expected_checks = EXPECTED_CHECK_NAMES[name]
    fresh_check_names = [check["name"] for check in fresh["checks"]]
    if fresh_check_names != expected_checks:
        print(f"STALE {name}-report.json: fresh checks do not match the current CLI contract")
        print(f"  Fresh:    {fresh_check_names!r}")
        print(f"  Expected: {expected_checks!r}")
        return False

    difference = first_contract_difference(committed, fresh)
    if difference:
        path, committed_value, fresh_value = difference
        print(f"STALE {name}-report.json: {path} differs")
        print(f"  Committed: {committed_value!r}")
        print(f"  Fresh:     {fresh_value!r}")
        return False

    print(f"OK {name}-report.json is up-to-date")
    return True


def main() -> int:
    outcomes = [check_report(name) for name in REPORT_NAMES]
    passed = all(outcomes)
    if not passed:
        print()
        print("Generate fresh diagnostic reports explicitly, then review and update committed snapshots:")
        print("  python -m forge_cli --root . validate --report out/validate-report.json")
        print("  python -m forge_cli --root . doctor --report out/doctor-report.json")
        return 1

    print("All reports are up-to-date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
