"""
check-module-paths.py — Verify every path registered in registry files actually exists on disk.
"""

import sys
import logging
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import FORGE_ROOT, WORKSPACE_ROOT, load_json, collect_ids, forge_path, workspace_path, file_exists, setup_logging, OK, FAIL

PATH_CONTAINING_FILES = [
    ("modules.json", "layers"),
    ("templates.json", "templates"),
    ("checklists.json", "checklists"),
]


def is_anchored_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    normalized = value.replace("\\", "/")
    return (
        PurePosixPath(normalized).is_absolute()
        or bool(PureWindowsPath(normalized).drive)
        or bool(PureWindowsPath(normalized).root)
    )


def resolve_path(entry: dict) -> Path:
    p = entry.get("path", "")
    # Normalize backslashes so a Windows form like ".codex\skills\SKILL.md"
    # resolves the same as the forward-slash form.
    p = p.replace("\\", "/") if isinstance(p, str) else p
    # Tool-prefixed paths are relative to the active tool directory
    # (WORKSPACE_ROOT). Strip the prefix to avoid double nesting.
    for prefix in (".claude/", ".codex/", ".cursor/"):
        if p.startswith(prefix):
            return workspace_path(p[len(prefix):])
    if p.startswith("./"):
        return forge_path(p[2:])
    return forge_path(p)


def is_within(base: Path, target: Path) -> bool:
    """True if `target` resolves to a path at or under `base`."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def check_paths(reg_name: str, key: str) -> int:
    reg_path = FORGE_ROOT / "registry" / reg_name
    data = load_json(reg_path)
    if data is None:
        return 1
    id_map = collect_ids(data, key)
    errors = 0
    for eid, entry in id_map.items():
        path_str = entry.get("path", "NO PATH")
        if is_anchored_path(path_str):
            print(f"  [{FAIL}] {eid} → {path_str}  (invalid or absolute registered path)")
            errors += 1
            continue
        resolved = resolve_path(entry)
        # Sandbox: a registered path must not escape the workspace root.
        # A path like "../../etc/passwd" would otherwise pass locally (if the
        # file happens to exist on the contributor's machine) and break for
        # everyone else.
        if not is_within(WORKSPACE_ROOT, resolved):
            print(f"  [{FAIL}] {eid} → {path_str}  (escapes workspace root: {resolved})")
            errors += 1
        elif file_exists(resolved):
            print(f"  [{OK}] {eid} → {path_str}")
        else:
            print(f"  [{FAIL}] {eid} → {path_str}  (not found: {resolved})")
            errors += 1
    return errors


def check_pack_paths() -> int:
    data = load_json(FORGE_ROOT / "registry" / "packs.json")
    if data is None:
        return 1
    errors = 0
    for pack in data.get("packs", []):
        path_str = pack.get("path", "")
        if is_anchored_path(path_str):
            print(f"  [{FAIL}] {pack.get('id', 'UNKNOWN')} → {path_str}  (invalid or absolute registered path)")
            errors += 1
            continue
        p = resolve_path(pack)
        if not is_within(WORKSPACE_ROOT, p):
            print(f"  [{FAIL}] {pack.get('id', 'UNKNOWN')} → {pack.get('path')}  (escapes workspace root: {p})")
            errors += 1
        elif file_exists(p):
            print(f"  [{OK}] {pack.get('id', 'UNKNOWN')} → {pack.get('path')}")
        else:
            print(f"  [{FAIL}] {pack.get('id', 'UNKNOWN')} → {pack.get('path')}  (not found: {p})")
            errors += 1
    return errors


def main() -> int:
    setup_logging()
    log = logging.getLogger("check-paths")
    log.debug("starting path verification")
    print("=== check-module-paths ===")
    errors = 0
    for reg_name, key in PATH_CONTAINING_FILES:
        print(f"\nChecking {reg_name} ({key})")
        errors += check_paths(reg_name, key)
    print("\nChecking packs.json (pack file paths)")
    errors += check_pack_paths()
    print()
    if errors:
        print(f"{FAIL} {errors} missing path(s).")
    else:
        print(f"{OK} All registered paths exist on disk.")
    return min(errors, 1)


if __name__ == "__main__":
    sys.exit(main())
