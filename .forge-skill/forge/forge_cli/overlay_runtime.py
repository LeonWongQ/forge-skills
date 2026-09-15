# -*- coding: utf-8 -*-
"""Read-only loading of the one active project Skill overlay."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .data_paths import forge_data_root, skill_data_root
from .learning_collector import _load_enabled_skills


def normalize_skill(value: str) -> str:
    return value.removeprefix("skill.").replace("_", "-").strip().lower()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _file_digest(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load_active_overlay(forge_root: Path, project: Path | None, skill: str) -> dict[str, Any] | None:
    """Load an ACTIVE overlay without creating or mutating project data.

    Overlay loading is deliberately fail-open: a missing, stale, corrupt, or
    cross-project overlay must never prevent the original Skill from running.
    """
    if project is None:
        return None
    project = project.resolve(strict=False)
    normalized_skill = normalize_skill(skill)
    if not normalized_skill or normalized_skill == "learning-collector":
        return None
    enabled_skills = _load_enabled_skills(forge_root, project)
    if enabled_skills is None or normalized_skill not in {
        normalize_skill(item) for item in enabled_skills
    }:
        return None

    identity = _read_json(project / ".forge-skill" / "learning" / "project.json")
    project_id = identity.get("projectId") if isinstance(identity, dict) else None
    if not isinstance(project_id, str) or not project_id.startswith("project-"):
        return None

    registry = _read_json(forge_data_root(forge_root) / "project-registry.json")
    entries = registry.get("projects", []) if isinstance(registry, dict) else []
    entry = next((item for item in entries if isinstance(item, dict) and item.get("projectId") == project_id), None)
    if not isinstance(entry, dict):
        return None
    registered_path = entry.get("path")
    if not isinstance(registered_path, str) or Path(registered_path).resolve(strict=False) != project:
        return None

    databases = entry.get("databases") if isinstance(entry.get("databases"), dict) else {}
    database_value = databases.get(normalized_skill)
    database = Path(database_value) if isinstance(database_value, str) else skill_data_root(forge_root, project_id, normalized_skill) / "learning.sqlite"
    if not database.is_file():
        return None

    try:
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=1)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT id, project_id, skill, version, status, content, manifest_json, content_digest, "
                "evaluation_json, published_at "
                "FROM skill_overlays WHERE project_id = ? AND skill = ? AND status = 'ACTIVE' "
                "ORDER BY version DESC LIMIT 1",
                (project_id, normalized_skill),
            ).fetchone()
        finally:
            connection.close()
    except (OSError, sqlite3.DatabaseError):
        return None
    if row is None:
        return None

    content = row["content"]
    digest = row["content_digest"]
    if not isinstance(content, str) or not isinstance(digest, str):
        return None
    calculated = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != calculated:
        return None
    manifest = _decode_manifest(row["manifest_json"])
    if not isinstance(manifest, dict) or manifest.get("executionSource") != "content":
        return None
    if manifest.get("projectId") != project_id or normalize_skill(str(manifest.get("skill", ""))) != normalized_skill:
        return None
    if manifest.get("contentDigest") not in (None, digest):
        return None
    evaluation = _decode_manifest(row["evaluation_json"])
    behavior = evaluation.get("behavior") if isinstance(evaluation, dict) else None
    if (not row["published_at"] or not isinstance(behavior, dict)
            or evaluation.get("passed") is not True or behavior.get("passed") is not True
            or behavior.get("candidateOverlayDigest") != digest):
        return None
    skill_digest = _file_digest(forge_root.parent / "skills" / normalized_skill / "SKILL.md")
    if skill_digest is None or behavior.get("skillDigest") != skill_digest:
        return None
    return {
        "id": row["id"],
        "projectId": project_id,
        "skill": normalized_skill,
        "version": row["version"],
        "content": content,
        "contentDigest": digest,
    }


def _decode_manifest(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except (UnicodeError, json.JSONDecodeError):
        return None
