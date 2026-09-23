#!/usr/bin/env python3
"""Start one direct-host Skill collection invocation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--forge-root", type=Path, default=None)
    parser.add_argument("--host", choices=("codex", "claude-code", "cursor"))
    args = parser.parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    forge_root = (args.forge_root or (skill_root.parent.parent / "forge")).resolve()
    sys.path.insert(0, str(forge_root))
    from forge_cli.learning_invocations import begin_invocation, current_host_from_environment

    current_host = args.host or current_host_from_environment() or "unknown"
    result = begin_invocation(
        forge_root, args.project, args.skill, current_host=current_host
    )
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
