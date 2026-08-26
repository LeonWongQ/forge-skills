"""Synchronize project-owned Forge skills into a Codex global skills overlay."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path

FORGE_ROOT = Path(__file__).resolve().parent.parent
if str(FORGE_ROOT) not in sys.path:
    sys.path.insert(0, str(FORGE_ROOT))

from forge_cli.codex_skill_sync import actions_as_json, apply_sync, default_codex_root, project_source_root, watch_sync


def polling_interval(value: str) -> float:
    interval = float(value)
    if interval < 0.2:
        raise argparse.ArgumentTypeError("--interval must be at least 0.2 seconds")
    return interval


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize Forge skills into an existing Codex global skills directory.")
    parser.add_argument("--target", type=Path, default=default_codex_root(), help="Codex root directory. Defaults to ~/.codex.")
    parser.add_argument("--check", action="store_true", help="Report missing links and conflicts without creating anything.")
    parser.add_argument("--watch", action="store_true", help="Keep watching for newly created skill folders.")
    parser.add_argument("--interval", type=polling_interval, default=600.0, help="Watch polling interval in seconds (default: 600; minimum: 0.2).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="Show links that are already synchronized.")
    return parser.parse_args(argv)


def render(actions, as_json: bool, verbose: bool = False) -> None:
    if as_json:
        print(json.dumps(actions_as_json(actions), ensure_ascii=False, indent=2))
        return
    visible = actions if verbose else [action for action in actions if action.status != "unchanged"]
    for action in visible:
        suffix = f" ({action.detail})" if action.detail else ""
        print(f"[{action.status.upper()}] {action.name}: {action.target}{suffix}")
    counts = Counter(action.status for action in actions)
    summary = ", ".join(f"{status}={counts[status]}" for status in sorted(counts))
    print(f"Summary: {summary or 'no actions'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = project_source_root(FORGE_ROOT)
    if args.watch and args.check:
        raise SystemExit("--watch cannot be combined with --check")
    if args.watch:
        try:
            for actions in watch_sync(source_root, args.target, args.interval):
                render(actions, args.json, args.verbose)
        except KeyboardInterrupt:
            return 0
        return 0

    actions = apply_sync(source_root, args.target, dry_run=args.check)
    render(actions, args.json, args.verbose)
    has_problem = any(action.status in {"create", "conflict", "source_missing"} for action in actions)
    return 1 if args.check and has_problem else 0


if __name__ == "__main__":
    raise SystemExit(main())
