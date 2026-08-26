#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate explicit, registry-derived facts published in Forge entry documents."""

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


FORGE_ROOT = Path(__file__).resolve().parent.parent
FACT_MARKER = "forge-facts"
FACT_PATTERN = re.compile(r"<!--\s*forge-facts:\s*(.*?)\s*-->")
INVENTORY_KEYS = ("skills", "packs", "domains", "checklists", "templates")
FULL_FACT_KEYS = (*INVENTORY_KEYS, "validation-count", "validation-checks", "version", "route-regression-count")
DOCUMENTS = {
    Path("../../README.md"): ("skills", "version", "route-regression-count", "skill-eval-case-count", "skill-eval-skill-count"),
    Path("README.md"): FULL_FACT_KEYS,
    Path("../rules/000-forge.mdc"): FULL_FACT_KEYS,
    Path("STATUS.md"): ("validation-count", "route-regression-count"),
    Path("docs/route-recommend-regression.md"): ("route-regression-count",),
    Path("../skills/forge/SKILL.md"): ("validation-count", "validation-checks"),
    Path("scripts/README.md"): ("skill-eval-case-count", "skill-eval-skill-count"),
    Path("../skills/README.md"): ("skills",),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def registry_facts(root: Path) -> dict[str, str]:
    registry = root / "registry"
    facts = {
        "skills": str(len(load_json(registry / "skills.json")["skills"])),
        "packs": str(len(load_json(registry / "packs.json")["packs"])),
        "domains": str(len(load_json(registry / "domains.json")["domains"])),
        "checklists": str(len(load_json(registry / "checklists.json")["checklists"])),
        "templates": str(len(load_json(registry / "templates.json")["templates"])),
    }

    constants_path = root / "forge_cli" / "constants.py"
    namespace: dict[str, Any] = {}
    exec(constants_path.read_text(encoding="utf-8"), namespace)
    checks = namespace["ALL_CHECKS"]
    facts["validation-count"] = str(len(checks))
    facts["validation-checks"] = ",".join(checks)
    facts["version"] = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    facts["route-regression-count"] = str(len(load_json(registry / "route-regression.json")["cases"]))
    behavior_cases = load_json(root / "evals" / "skill-behavior-cases.json")["cases"]
    facts["skill-eval-case-count"] = str(len(behavior_cases))
    facts["skill-eval-skill-count"] = str(len({case["skill"] for case in behavior_cases}))
    return facts


def parse_markers(document: Path) -> list[dict[str, str]]:
    markers = FACT_PATTERN.findall(document.read_text(encoding="utf-8"))
    parsed = []
    for marker in markers:
        values: dict[str, str] = {}
        for token in marker.split():
            if "=" not in token:
                raise ValueError(f"invalid {FACT_MARKER} token {token!r}")
            key, value = token.split("=", 1)
            values[key] = value
        parsed.append(values)
    return parsed


def validate_documentation_facts(root: Path) -> list[str]:
    facts = registry_facts(root)
    issues: list[str] = []

    project_version = load_json(root / "registry" / "project.json").get("version")
    if project_version != facts["version"]:
        issues.append(
            "registry/project.json: "
            f"version={project_version!r}, package version={facts['version']!r}"
        )

    for relative_path, required in DOCUMENTS.items():
        document = root / relative_path
        if not document.is_file():
            issues.append(f"missing designated document: {relative_path}")
            continue

        try:
            markers = parse_markers(document)
        except ValueError as error:
            issues.append(f"{relative_path}: {error}")
            continue

        if not markers:
            issues.append(f"{relative_path}: missing <!-- {FACT_MARKER}: ... --> marker")
            continue

        declared = {key: value for marker in markers for key, value in marker.items()}
        for key in required:
            expected = facts[key]
            actual = declared.get(key)
            if actual is None:
                issues.append(f"{relative_path}: missing {key} fact marker (expected {expected})")
            elif actual != expected:
                issues.append(f"{relative_path}: {key}={actual!r}, expected {expected!r}")

    return issues


def main() -> int:
    issues = validate_documentation_facts(FORGE_ROOT)
    if issues:
        print("Documentation facts validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    facts = registry_facts(FORGE_ROOT)
    print(
        "Documentation facts valid: "
        f"v{facts['version']}, {facts['skills']} skills, {facts['packs']} packs, "
        f"{facts['validation-count']} validation checks, "
        f"{facts['route-regression-count']} route regression cases, "
        f"{facts['skill-eval-case-count']} behavior cases across "
        f"{facts['skill-eval-skill-count']} skills."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
