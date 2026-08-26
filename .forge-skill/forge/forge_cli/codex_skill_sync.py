"""Safely expose project-owned Forge skills through a Codex global skills directory."""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from time import sleep
from typing import Callable, Iterable


@dataclass(frozen=True)
class SyncAction:
    name: str
    source: Path
    target: Path
    status: str
    detail: str | None = None


def project_source_root(forge_root: Path) -> Path:
    """Return the host directory that contains the Forge checkout."""
    return forge_root.resolve(strict=False).parent


def default_codex_root() -> Path:
    return Path.home() / ".codex"


def source_skill_directories(source_root: Path) -> list[Path]:
    skills_root = source_root / "skills"
    if not skills_root.is_dir():
        raise ValueError(f"Forge skills directory does not exist: {skills_root}")
    return sorted(
        (path for path in skills_root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()),
        key=lambda path: path.name.casefold(),
    )


def _link_target(path: Path) -> Path | None:
    try:
        value = os.readlink(path)
    except OSError:
        return None
    target = Path(value)
    return target if target.is_absolute() else path.parent / target


def _same_path(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        pass
    return os.path.normcase(os.path.normpath(str(left.resolve(strict=False)))) == os.path.normcase(
        os.path.normpath(str(right.resolve(strict=False)))
    )


def plan_sync(source_root: Path, codex_root: Path) -> list[SyncAction]:
    """Plan a non-destructive Forge + skills overlay without changing either tree."""
    source_root = source_root.resolve(strict=False)
    codex_root = codex_root.resolve(strict=False)
    sources = [("forge", source_root / "forge", codex_root / "forge")]
    sources.extend((skill.name, skill, codex_root / "skills" / skill.name) for skill in source_skill_directories(source_root))

    actions: list[SyncAction] = []
    for name, source, target in sources:
        if not source.is_dir():
            actions.append(SyncAction(name, source, target, "source_missing"))
        elif not os.path.lexists(target):
            actions.append(SyncAction(name, source, target, "create"))
        else:
            existing = _link_target(target)
            if existing is not None and _same_path(existing, source):
                actions.append(SyncAction(name, source, target, "unchanged", "Already linked to project source."))
            else:
                actions.append(SyncAction(name, source, target, "conflict", "Existing global path is preserved."))
    return actions


def create_junction(target: Path, source: Path) -> None:
    """Create one Windows directory Junction without shell interpolation."""
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(target), str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        detail = (completed.stdout + completed.stderr).strip()
        raise OSError(detail or f"Unable to create Junction: {target}")


def apply_sync(
    source_root: Path,
    codex_root: Path,
    *,
    dry_run: bool = False,
    create_link: Callable[[Path, Path], None] = create_junction,
) -> list[SyncAction]:
    """Create only missing links. Existing files, directories, and links are never replaced."""
    actions = plan_sync(source_root, codex_root)
    if dry_run:
        return actions

    for action in actions:
        if action.status != "create":
            continue
        action.target.parent.mkdir(parents=True, exist_ok=True)
        create_link(action.target, action.source)
    return actions


def source_snapshot(source_root: Path) -> tuple[str, ...]:
    return tuple(skill.name for skill in source_skill_directories(source_root))


def watch_sync(source_root: Path, codex_root: Path, interval_seconds: float) -> Iterable[list[SyncAction]]:
    """Yield the initial sync and each later sync when a skill directory changes."""
    if interval_seconds < 0.2:
        raise ValueError("Watch interval must be at least 0.2 seconds.")
    snapshot: tuple[str, ...] | None = None
    while True:
        current = source_snapshot(source_root)
        if current != snapshot:
            snapshot = current
            yield apply_sync(source_root, codex_root)
        sleep(interval_seconds)


def actions_as_json(actions: list[SyncAction]) -> list[dict[str, str | None]]:
    return [
        {key: str(value) if isinstance(value, Path) else value for key, value in asdict(action).items()}
        for action in actions
    ]
