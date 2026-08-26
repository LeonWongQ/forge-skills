"""Project-owned Forge Runtime path policy and legacy migration."""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_RUNTIME_DIRECTORY = ".forge-runtime"
LEGACY_RUNTIME_DIRECTORY = ".forge" + "/runtime"


def project_runtime_directory(project: Path) -> Path:
    return project.resolve() / PROJECT_RUNTIME_DIRECTORY


def validate_project_runtime_directory(directory: Path, project: Path | None = None) -> Path:
    expected = project_runtime_directory(project or Path.cwd())
    resolved = directory.resolve()
    if resolved != expected:
        raise ValueError(
            "runtime directory must be the current project's .forge-runtime directory; "
            "global stores must be partitioned by project id"
        )
    return resolved


def migrate_legacy_runtime_directory(project: Path) -> list[dict[str, str]]:
    """Move legacy runtime files without overwriting newer project state."""
    legacy = project.resolve() / LEGACY_RUNTIME_DIRECTORY
    target = project_runtime_directory(project)
    if not legacy.is_dir():
        return []
    target.mkdir(parents=True, exist_ok=True)
    diagnostics: list[dict[str, str]] = []
    for source in sorted(legacy.iterdir(), key=lambda item: item.name.lower()):
        if not source.is_file():
            continue
        destination = target / source.name
        if destination.exists():
            diagnostics.append({"code": "LEGACY_RUNTIME_CONFLICT", "path": source.name})
            continue
        try:
            shutil.move(str(source), str(destination))
        except OSError as error:
            diagnostics.append({
                "code": "LEGACY_RUNTIME_MIGRATION_FAILED",
                "path": source.name,
                "message": str(error),
            })
    return diagnostics
