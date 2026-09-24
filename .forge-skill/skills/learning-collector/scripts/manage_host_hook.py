#!/usr/bin/env python3
"""Configure, inspect, or remove the user-global native learning Hook."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "configure", "remove"))
    parser.add_argument("--host", choices=("codex", "claude-code", "cursor"))
    parser.add_argument("--forge-root", type=Path, default=None)
    args = parser.parse_args()
    if args.action == "configure" and args.host is None:
        parser.error("--host is required for configure")
    skill_root = Path(__file__).resolve().parents[1]
    forge_root = (args.forge_root or (skill_root.parent.parent / "forge")).resolve()
    sys.path.insert(0, str(forge_root))
    from forge_cli.learning_hook_manager import (
        configure_global_hook,
        global_hook_status,
        remove_global_hook,
    )

    if args.action == "configure":
        result = configure_global_hook(forge_root, args.host)
    elif args.action == "remove":
        result = remove_global_hook(forge_root, args.host)
    else:
        result = global_hook_status(forge_root)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
