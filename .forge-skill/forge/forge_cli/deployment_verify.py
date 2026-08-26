# -*- coding: utf-8 -*-
"""Dependency-free source entry point for Forge deployment verification."""

import argparse
import sys
from pathlib import Path

from .deployment_verification import verify_deployment

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_USAGE_ERROR = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Forge directory-junction deployment without modifying files."
    )
    parser.add_argument("--project", required=True, type=Path, help="Consumer project directory")
    parser.add_argument(
        "--tool",
        required=True,
        choices=("claude", "cursor", "codex"),
        help="Consumer tool layout",
    )
    parser.add_argument(
        "--source-root",
        required=True,
        type=Path,
        help="Source .claude directory containing forge and skills",
    )
    return parser


def _render(result: dict) -> None:
    print("Forge deployment verification")
    print(f"Project: {result['project']}")
    print(f"Tool: {result['tool']}")
    print(f"Source: {result['source_root']}")

    if result.get("environment_error"):
        print(f"[FAIL] environment {result['environment_error']}")
    else:
        for item in result["items"]:
            status = item["status"].upper()
            print(f"[{status}] {item['name']} {item['code']}")

    summary = result["summary"]
    outcome = "PASS" if result["ok"] else "FAIL"
    print(
        f"Summary: {outcome} ({summary['verified']} verified, "
        f"{summary['failed']} failed, {summary['skipped']} skipped)"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = verify_deployment(args.project, args.tool, args.source_root)
    _render(result)
    if result.get("environment_error"):
        return EXIT_USAGE_ERROR
    return EXIT_OK if result["ok"] else EXIT_VALIDATION_FAILED


if __name__ == "__main__":
    sys.exit(main())
