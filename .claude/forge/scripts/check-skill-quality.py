#!/usr/bin/env python3
"""Validate repository-owned skills and their user-facing metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


FORGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = FORGE_ROOT.parent.parent
SKILLS_ROOT = FORGE_ROOT.parent / "skills"
SKILLS_REGISTRY = FORGE_ROOT / "registry" / "skills.json"
ALLOWED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
}
LOCAL_REFERENCE_PATTERN = re.compile(
    r"(?<![\w])((?:\.claude/forge/|\.claude/skills/|references/|scripts/|assets/)"
    r"[A-Za-z0-9_.\-/]*[A-Za-z0-9_-]+\.[A-Za-z0-9]+)"
)
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MAX_SKILL_LINES = 220
MIN_DUPLICATE_PARAGRAPH_CHARS = 240


def load_yaml(path: Path, label: str, errors: list[str]) -> object | None:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(f"{label}: cannot read valid UTF-8 YAML: {exc}")
        return None


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    label = skill_dir.name

    try:
        content = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{label}: cannot read SKILL.md as UTF-8: {exc}"]

    line_count = len(content.splitlines())
    if line_count > MAX_SKILL_LINES:
        errors.append(
            f"{label}: SKILL.md has {line_count} lines; maximum is {MAX_SKILL_LINES}. "
            "Move mode-specific detail into a linked reference."
        )

    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
    if not match:
        errors.append(f"{label}: SKILL.md has invalid YAML frontmatter delimiters")
        return errors

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{label}: invalid SKILL.md frontmatter YAML: {exc}")
        return errors

    if not isinstance(frontmatter, dict):
        errors.append(f"{label}: SKILL.md frontmatter must be a mapping")
        return errors

    body_start = content[: match.end()].count("\n") + 1
    for line_number, line in enumerate(content[match.end():].splitlines(), start=body_start):
        if CJK_PATTERN.search(line):
            errors.append(
                f"{label}: SKILL.md explanatory body must be English; "
                f"CJK text found on line {line_number}"
            )

    unexpected = sorted(set(frontmatter) - ALLOWED_FRONTMATTER_KEYS)
    if unexpected:
        errors.append(f"{label}: unsupported frontmatter keys: {', '.join(unexpected)}")

    name = frontmatter.get("name")
    if name != label:
        errors.append(f"{label}: frontmatter name must match its directory name")
    if not isinstance(frontmatter.get("description"), str) or not frontmatter["description"].strip():
        errors.append(f"{label}: frontmatter description must be a non-empty string")

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not openai_yaml.is_file():
        errors.append(f"{label}: missing agents/openai.yaml")
    else:
        metadata = load_yaml(openai_yaml, f"{label}/agents/openai.yaml", errors)
        if isinstance(metadata, dict):
            interface = metadata.get("interface")
            if not isinstance(interface, dict):
                errors.append(f"{label}: openai.yaml interface must be a mapping")
            else:
                display_name = interface.get("display_name")
                short_description = interface.get("short_description")
                default_prompt = interface.get("default_prompt")
                if not isinstance(display_name, str) or not display_name.strip():
                    errors.append(f"{label}: display_name must be a non-empty string")
                if not isinstance(short_description, str) or not 25 <= len(short_description) <= 64:
                    errors.append(f"{label}: short_description must contain 25-64 characters")
                if not isinstance(default_prompt, str) or f"${label}" not in default_prompt:
                    errors.append(f"{label}: default_prompt must explicitly mention ${label}")

    for reference in sorted(set(LOCAL_REFERENCE_PATTERN.findall(content))):
        clean_reference = reference.rstrip(".,;:)")
        target = (
            REPO_ROOT / clean_reference
            if clean_reference.startswith((".claude/forge/", ".claude/skills/"))
            else skill_dir / clean_reference
        )
        if not target.exists():
            errors.append(f"{label}: referenced local path does not exist: {clean_reference}")

    return errors


def validate_registry_coverage(skill_dirs: list[Path]) -> list[str]:
    try:
        payload = yaml.safe_load(SKILLS_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [f"skills registry: cannot read valid UTF-8 JSON/YAML: {exc}"]
    entries = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return ["skills registry: skills must be an array"]
    registered = {
        entry.get("name") for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    on_disk = {path.name for path in skill_dirs}
    errors = [f"skills registry: unregistered skill directory: {name}" for name in sorted(on_disk - registered)]
    errors.extend(f"skills registry: registered skill directory is missing: {name}" for name in sorted(registered - on_disk))
    return errors


def validate_duplicate_paragraphs(skill_dirs: list[Path]) -> list[str]:
    """Reject long verbatim guidance copied across multiple Skill entrypoints."""
    occurrences: dict[str, set[str]] = {}
    for skill_dir in skill_dirs:
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\r?\n.*?\r?\n---(?:\r?\n|$)", content, re.DOTALL)
        body = content[match.end():] if match else content
        for paragraph in re.split(r"(?:\r?\n){2,}", body):
            normalized = " ".join(paragraph.split())
            if (
                len(normalized) < MIN_DUPLICATE_PARAGRAPH_CHARS
                or normalized.startswith("```")
                or ".claude/forge/references/" in normalized
            ):
                continue
            occurrences.setdefault(normalized, set()).add(skill_dir.name)

    errors = []
    for paragraph, skills in sorted(occurrences.items()):
        if len(skills) < 2:
            continue
        preview = paragraph[:80] + ("..." if len(paragraph) > 80 else "")
        errors.append(
            f"duplicate long guidance in {', '.join(sorted(skills))}: {preview!r}; "
            "move shared policy into a linked Forge reference"
        )
    return errors


def main() -> int:
    if not SKILLS_ROOT.is_dir():
        print(f"[FAIL] skills directory not found: {SKILLS_ROOT}", file=sys.stderr)
        return 1

    skill_dirs = sorted(
        path for path in SKILLS_ROOT.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()
    )
    errors = [error for skill_dir in skill_dirs for error in validate_skill(skill_dir)]
    errors.extend(validate_registry_coverage(skill_dirs))
    errors.extend(validate_duplicate_paragraphs(skill_dirs))
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        print(f"Skill quality check failed with {len(errors)} error(s).", file=sys.stderr)
        return 1

    print(f"Skill quality check passed for {len(skill_dirs)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
