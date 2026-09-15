#!/usr/bin/env python3
"""Resolve one active project Skill Overlay for a direct host invocation."""
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
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    forge_root = (args.forge_root or (skill_root.parent.parent / "forge")).resolve()
    sys.path.insert(0, str(forge_root))
    from forge_cli.overlay_runtime import load_active_overlay

    overlay = load_active_overlay(forge_root, args.project, args.skill)
    print(json.dumps({"overlay": overlay}, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
