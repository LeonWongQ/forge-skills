"""Canonical paths for Forge-generated runtime data."""

from __future__ import annotations

import os
from pathlib import Path


FORGE_DATA_DIRECTORY = "forge-data"


def forge_data_root(forge_root: Path) -> Path:
    """Resolve the shared data root beside the physical Forge installation.

    ``FORGE_DATA_ROOT`` is an explicit override for packaged deployments. In
    the source tree this resolves to ``.forge-skill/forge-data``; when Forge
    is linked from a global installation it resolves to ``<home>/forge-data``.
    """
    configured = os.getenv("FORGE_DATA_ROOT")
    if configured and configured.strip():
        return Path(configured).expanduser().resolve(strict=False)
    # Keep the logical installation path. Resolving a Junction would point
    # global installs back into the source checkout and split runtime data.
    logical_root = forge_root.absolute()
    return logical_root.parent / FORGE_DATA_DIRECTORY


def project_data_root(forge_root: Path, project_id: str) -> Path:
    if not project_id or Path(project_id).name != project_id:
        raise ValueError("invalid Forge project id")
    return forge_data_root(forge_root) / "projects" / project_id


def project_runtime_data_root(forge_root: Path, project_id: str) -> Path:
    return project_data_root(forge_root, project_id) / "runtime" / "paused"


def skill_data_root(forge_root: Path, project_id: str, skill: str) -> Path:
    if not skill or Path(skill).name != skill or skill in {".", ".."}:
        raise ValueError("invalid Forge Skill id")
    return project_data_root(forge_root, project_id) / "learning" / skill
