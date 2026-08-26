#!/usr/bin/env python3
"""Validate the versioned skill behavior forward-test corpus."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


FORGE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = FORGE_ROOT.parent / "skills"
CORPUS_PATH = FORGE_ROOT / "evals" / "skill-behavior-cases.json"
VALID_CATEGORIES = {"representative", "boundary", "known_failure", "adversarial"}
VALID_CAPABILITIES = {"browser", "filesystem_read", "filesystem_write", "shell"}
REQUIRED_RISK_SKILLS = {
    "auto-compact",
    "bailian-api",
    "bailian-workflow",
    "forge",
    "llm-evaluation",
    "page-test",
}
VALID_FIXTURES = {
    "ambiguous-services",
    "browser-missing",
    "empty",
    "local-documentation",
    "login-test",
    "playwright-diagnosis",
    "retry-service",
    "review-target",
    "security-target",
    "release-candidate",
    "contract-change",
    "migration-target",
    "test-target",
    "dependency-target",
}
CASE_ID_PATTERN = re.compile(r"^skill-eval\.[a-z0-9-]+\.[a-z0-9-]+$")


def _nonempty_strings(value: object, minimum: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def validate_corpus(path: Path = CORPUS_PATH, skills_root: Path = SKILLS_ROOT) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read valid UTF-8 JSON from {path}: {exc}"]

    if not isinstance(payload, dict):
        return ["corpus root must be an object"]
    if payload.get("version") != 1:
        errors.append("corpus version must be 1")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty array"]

    seen_ids: set[str] = set()
    categories: Counter[str] = Counter()
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
            errors.append(f"{label}.id must match {CASE_ID_PATTERN.pattern}")
        elif case_id in seen_ids:
            errors.append(f"duplicate case id: {case_id}")
        else:
            seen_ids.add(case_id)

        skill = case.get("skill")
        if not isinstance(skill, str) or not (skills_root / skill / "SKILL.md").is_file():
            errors.append(f"{label}.skill must reference an existing skill")
        category = case.get("category")
        if category not in VALID_CATEGORIES:
            errors.append(f"{label}.category must be one of {sorted(VALID_CATEGORIES)}")
        else:
            categories[category] += 1
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{label}.prompt must be a non-empty string")
        execution = case.get("execution")
        if not isinstance(execution, dict):
            errors.append(f"{label}.execution must be an object")
        else:
            if execution.get("fixture") not in VALID_FIXTURES:
                errors.append(f"{label}.execution.fixture is unsupported")
            if execution.get("sandbox") not in {"read-only", "workspace-write"}:
                errors.append(f"{label}.execution.sandbox must be read-only or workspace-write")
            timeout = execution.get("timeout_seconds")
            if not isinstance(timeout, int) or not 30 <= timeout <= 300:
                errors.append(f"{label}.execution.timeout_seconds must be an integer from 30 to 300")
            mode = execution.get("mode")
            if mode not in {"automated", "environment_gated"}:
                errors.append(f"{label}.execution.mode is unsupported")
            if mode == "environment_gated" and not isinstance(execution.get("requires"), str):
                errors.append(f"{label}.execution.requires must describe the environment gate")
            capabilities = execution.get("requires_capabilities")
            if not _nonempty_strings(capabilities):
                errors.append(f"{label}.execution.requires_capabilities must contain at least one string")
            elif unknown := sorted(set(capabilities) - VALID_CAPABILITIES):
                errors.append(
                    f"{label}.execution.requires_capabilities contains unsupported values: {', '.join(unknown)}"
                )
        if not _nonempty_strings(case.get("hard_requirements"), minimum=2):
            errors.append(f"{label}.hard_requirements must contain at least two strings")
        if not _nonempty_strings(case.get("forbidden_behaviors")):
            errors.append(f"{label}.forbidden_behaviors must contain at least one string")

    missing_categories = sorted(VALID_CATEGORIES - set(categories))
    if missing_categories:
        errors.append(f"corpus is missing categories: {', '.join(missing_categories)}")
    distinct_skills = {case.get("skill") for case in cases if isinstance(case, dict)}
    if path == CORPUS_PATH:
        repository_skills = {
            skill_dir.name
            for skill_dir in skills_root.iterdir()
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file()
        }
        missing_skills = sorted(repository_skills - distinct_skills)
        if missing_skills:
            errors.append(
                "repository corpus must cover every Skill; missing: "
                + ", ".join(missing_skills)
            )
        missing_risk_skills = sorted(REQUIRED_RISK_SKILLS - distinct_skills)
        if missing_risk_skills:
            errors.append(
                "repository corpus is missing risk-critical skills: "
                + ", ".join(missing_risk_skills)
            )
    return errors


def main() -> int:
    errors = validate_corpus()
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    counts = Counter(case["category"] for case in payload["cases"])
    summary = ", ".join(f"{category}={counts[category]}" for category in sorted(counts))
    skill_count = len({case["skill"] for case in payload["cases"]})
    print(f"Skill behavior corpus valid: {len(payload['cases'])} cases across {skill_count} skills ({summary}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
