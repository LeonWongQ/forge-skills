"""Safely expose project-owned skills to supported coding agents."""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from time import sleep
from typing import Callable, Iterable

from .paths import CLIENT_DIRECTORIES, SKILL_METADATA_FILE, SKILLS_DIRECTORY, client_skills_root

SUPPORTED_CLIENTS = tuple(CLIENT_DIRECTORIES)


@dataclass(frozen=True)
class SkillSyncAction:
    name: str
    source: Path
    target: Path
    status: str
    detail: str | None = None


def project_source_root(forge_root: Path) -> Path:
    return forge_root.resolve(strict=False).parent


def source_skill_directories(source_root: Path) -> list[Path]:
    skills_root = source_root / SKILLS_DIRECTORY
    if not skills_root.is_dir():
        raise ValueError(f"Forge skills directory does not exist: {skills_root}")
    return sorted(
        (path for path in skills_root.iterdir() if path.is_dir() and (path / SKILL_METADATA_FILE).is_file()),
        key=lambda path: path.name.casefold(),
    )


def resolve_skills_root(
    client: str,
    scope: str,
    *,
    project: Path | None = None,
    home: Path | None = None,
    target: Path | None = None,
) -> Path:
    if client not in SUPPORTED_CLIENTS:
        raise ValueError(f"unsupported client: {client}")
    if scope not in {"global", "project"}:
        raise ValueError(f"unsupported scope: {scope}")
    if target is not None:
        return target.resolve(strict=False)
    if scope == "global":
        return client_skills_root(home or Path.home(), client).resolve(strict=False)
    if project is None:
        raise ValueError("--project is required when --scope project is selected")
    project = project.resolve(strict=False)
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    return client_skills_root(project, client).resolve(strict=False)


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
        return os.path.normcase(os.path.normpath(str(left.resolve(strict=False)))) == os.path.normcase(
            os.path.normpath(str(right.resolve(strict=False)))
        )


def plan_sync(source_root: Path, skills_root: Path) -> list[SkillSyncAction]:
    source_root = source_root.resolve(strict=False)
    skills_root = skills_root.resolve(strict=False)
    actions = []
    for source in source_skill_directories(source_root):
        target = skills_root / source.name
        if not os.path.lexists(target):
            actions.append(SkillSyncAction(source.name, source, target, "create"))
            continue
        existing = _link_target(target)
        if existing is not None and _same_path(existing, source):
            actions.append(SkillSyncAction(source.name, source, target, "unchanged", "Already linked to project source."))
        else:
            actions.append(SkillSyncAction(source.name, source, target, "conflict", "Existing path is preserved."))
    return actions


def create_directory_link(target: Path, source: Path) -> None:
    if os.name == "nt":
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
        return
    target.symlink_to(source, target_is_directory=True)


def remove_directory_link(target: Path) -> None:
    if target.is_symlink():
        target.unlink()
    else:
        target.rmdir()


def apply_sync(
    source_root: Path,
    skills_root: Path,
    *,
    dry_run: bool = False,
    create_link: Callable[[Path, Path], None] = create_directory_link,
    remove_link: Callable[[Path], None] = remove_directory_link,
) -> list[SkillSyncAction]:
    actions = plan_sync(source_root, skills_root)
    if dry_run:
        return actions
    created = []
    try:
        for action in actions:
            if action.status != "create":
                continue
            action.target.parent.mkdir(parents=True, exist_ok=True)
            create_link(action.target, action.source)
            created.append(action.target)
    except BaseException as error:
        rollback_errors = []
        for target in reversed(created):
            try:
                remove_link(target)
            except OSError as rollback_error:
                rollback_errors.append(f"{target}: {rollback_error}")
        if rollback_errors:
            raise OSError(
                f"{error}; rollback failed for: {'; '.join(rollback_errors)}"
            ) from error
        raise
    return actions


def plan_uninstall(source_root: Path, skills_root: Path) -> list[SkillSyncAction]:
    """Plan removal of only links that still point to this Forge source."""
    source_root = source_root.resolve(strict=False)
    skills_root = skills_root.resolve(strict=False)
    if not skills_root.is_dir():
        return []
    actions = []
    for source in source_skill_directories(source_root):
        target = skills_root / source.name
        existing = _link_target(target) if os.path.lexists(target) else None
        if existing is not None and _same_path(existing, source):
            actions.append(SkillSyncAction(source.name, source, target, "remove"))
        elif os.path.lexists(target):
            actions.append(SkillSyncAction(source.name, source, target, "preserved", "Existing path is not a Forge link."))
    return actions


def apply_uninstall(source_root: Path, skills_root: Path, *, dry_run: bool = False) -> list[SkillSyncAction]:
    actions = plan_uninstall(source_root, skills_root)
    if dry_run:
        return actions
    for action in actions:
        if action.status != "remove":
            continue
        remove_directory_link(action.target)
    return actions


def source_snapshot(source_root: Path) -> tuple[str, ...]:
    return tuple(skill.name for skill in source_skill_directories(source_root))


def watch_sync(source_root: Path, skills_root: Path, interval_seconds: float) -> Iterable[list[SkillSyncAction]]:
    if interval_seconds < 0.2:
        raise ValueError("Watch interval must be at least 0.2 seconds.")
    snapshot = None
    while True:
        current = source_snapshot(source_root)
        if current != snapshot:
            snapshot = current
            yield apply_sync(source_root, skills_root)
        sleep(interval_seconds)


def actions_as_json(actions: list[SkillSyncAction]) -> list[dict[str, str | None]]:
    return [
        {key: str(value) if isinstance(value, Path) else value for key, value in asdict(action).items()}
        for action in actions
    ]
