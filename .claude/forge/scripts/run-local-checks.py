#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the non-mutating Forge quality gate in quick or full mode."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
Step = tuple[str, list[str]]


def run_step(number: int, total: int, label: str, command: list[str]) -> int:
    print(f"[{number}/{total}] {label}", flush=True)
    env = os.environ.copy()
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    proc = subprocess.run(command, cwd=FORGE_ROOT, env=env)
    if proc.returncode:
        print(f"[FAIL] {label} exited with {proc.returncode}", file=sys.stderr)
    return proc.returncode


def build_steps(mode: str, pytest_temp: str | None = None) -> list[Step]:
    steps: list[Step] = [
        ("text integrity", [sys.executable, str(FORGE_ROOT / "scripts" / "check-text-integrity.py")]),
        ("sensitive content", [sys.executable, str(FORGE_ROOT / "scripts" / "check-sensitive-content.py")]),
        ("skill quality", [sys.executable, str(FORGE_ROOT / "scripts" / "check-skill-quality.py")]),
        ("skill eval corpus", [sys.executable, str(FORGE_ROOT / "scripts" / "check-skill-eval-corpus.py")]),
        ("validate", [sys.executable, "-m", "forge_cli", "--root", str(FORGE_ROOT), "validate"]),
    ]
    if mode == "quick":
        return steps
    if mode != "full":
        raise ValueError(f"unsupported quality gate mode: {mode}")
    if pytest_temp is None:
        raise ValueError("pytest_temp is required for the full quality gate")
    return steps + [
        ("route regression", [sys.executable, str(FORGE_ROOT / "scripts" / "check-route-regression.py")]),
        ("documentation facts", [sys.executable, str(FORGE_ROOT / "scripts" / "check-documentation-facts.py")]),
        ("pytest", [sys.executable, "-m", "pytest", "-q", "--basetemp", pytest_temp]),
    ]


def run_steps(steps: list[Step]) -> int:
    for index, (label, command) in enumerate(steps, start=1):
        if run_step(index, len(steps), label, command):
            return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true", help="run the commit-time gate")
    mode.add_argument("--full", action="store_true", help="run all checks (the default)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "quick" if args.quick else "full"
    print("=" * 50)
    print(f"Forge Local Quality Gate ({mode})")
    print(f"Forge Root: {FORGE_ROOT}")
    print("=" * 50)

    if mode == "quick":
        if run_steps(build_steps(mode)):
            return 1
    else:
        with tempfile.TemporaryDirectory(prefix="forge-pytest-") as pytest_temp:
            if run_steps(build_steps(mode, pytest_temp)):
                return 1

    print("=" * 50)
    print(f"All {mode} quality checks passed.")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
