"""Canonical Forge repository and client path definitions."""

from __future__ import annotations

from pathlib import Path


SOURCE_CONTAINER = ".forge-skill"
FORGE_DIRECTORY = "forge"
SKILLS_DIRECTORY = "skills"
RULES_DIRECTORY = "rules"
SKILL_METADATA_FILE = "SKILL.md"

CLIENT_DIRECTORIES = {
    "claude": ".claude",
    "codex": ".codex",
    "cursor": ".cursor",
}


def repository_source_root(repository_root: Path) -> Path:
    return repository_root / SOURCE_CONTAINER


def forge_source_root(repository_root: Path) -> Path:
    return repository_source_root(repository_root) / FORGE_DIRECTORY


def skills_source_root(repository_root: Path) -> Path:
    return repository_source_root(repository_root) / SKILLS_DIRECTORY


def client_skills_root(home: Path, client: str) -> Path:
    try:
        client_directory = CLIENT_DIRECTORIES[client]
    except KeyError as error:
        raise ValueError(f"unsupported client: {client}") from error
    return home / client_directory / SKILLS_DIRECTORY
