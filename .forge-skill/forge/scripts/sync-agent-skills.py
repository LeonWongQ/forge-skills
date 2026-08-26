#!/usr/bin/env python3
"""Synchronize Forge skills into a Codex, Claude, or Cursor skill directory."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
if str(FORGE_ROOT) not in sys.path:
    sys.path.insert(0, str(FORGE_ROOT))

from forge_cli.agent_skill_sync import (
    SUPPORTED_CLIENTS,
    actions_as_json,
    apply_sync,
    apply_uninstall,
    project_source_root,
    resolve_skills_root,
    watch_sync,
)


def polling_interval(value: str) -> float:
    interval = float(value)
    if interval < 0.2:
        raise argparse.ArgumentTypeError("--interval must be at least 0.2 seconds")
    return interval


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=SUPPORTED_CLIENTS, required=True, help="Target coding agent.")
    parser.add_argument("--scope", choices=("global", "project"), required=True, help="Install for the current user or one project.")
    parser.add_argument("--project", type=Path, help="Project root; required with --scope project.")
    parser.add_argument("--target", type=Path, help="Advanced override for the exact target skills directory.")
    parser.add_argument("--check", action="store_true", help="Report missing links and conflicts without creating anything.")
    parser.add_argument("--uninstall", action="store_true", help="Remove only links created from this Forge source.")
    parser.add_argument("--watch", action="store_true", help="Watch the source and link newly added skills.")
    parser.add_argument("--interval", type=polling_interval, default=600.0, help="Watch interval in seconds (default: 600).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="Show skills that are already synchronized.")
    return parser.parse_args(argv)


def render(actions, *, client: str, scope: str, skills_root: Path, as_json: bool, verbose: bool) -> None:
    if as_json:
        print(json.dumps({
            "client": client,
            "scope": scope,
            "skills_root": str(skills_root),
            "actions": actions_as_json(actions),
        }, ensure_ascii=False, indent=2))
        return
    print(f"Target: {client} {scope} skills at {skills_root}")
    visible = actions if verbose else [action for action in actions if action.status != "unchanged"]
    for action in visible:
        suffix = f" ({action.detail})" if action.detail else ""
        print(f"[{action.status.upper()}] {action.name}: {action.target}{suffix}")
    counts = Counter(action.status for action in actions)
    summary = ", ".join(f"{status}={counts[status]}" for status in sorted(counts))
    print(f"Summary: {summary or 'no actions'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.watch and args.check:
        raise SystemExit("error: --watch cannot be combined with --check")
    if args.watch and args.uninstall:
        raise SystemExit("error: --watch cannot be combined with --uninstall")
    if args.scope == "global" and args.project:
        raise SystemExit("error: --project is valid only with --scope project")
    if args.target and args.project:
        raise SystemExit("error: use either --target or --project, not both")
    try:
        skills_root = resolve_skills_root(args.client, args.scope, project=args.project, target=args.target)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from None
    source_root = project_source_root(FORGE_ROOT)
    if args.watch:
        try:
            for actions in watch_sync(source_root, skills_root, args.interval):
                render(actions, client=args.client, scope=args.scope, skills_root=skills_root, as_json=args.json, verbose=args.verbose)
        except KeyboardInterrupt:
            return 0
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0
    try:
        actions = (apply_uninstall if args.uninstall else apply_sync)(source_root, skills_root, dry_run=args.check)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    render(actions, client=args.client, scope=args.scope, skills_root=skills_root, as_json=args.json, verbose=args.verbose)
    has_problem = any(action.status in {"create", "conflict", "remove"} for action in actions)
    return 1 if args.check and has_problem else 0


if __name__ == "__main__":
    raise SystemExit(main())
