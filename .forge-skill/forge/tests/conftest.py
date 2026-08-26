# -*- coding: utf-8 -*-
"""Shared fixtures for Forge CLI tests."""

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def forge_root(tmp_path):
    """Create a minimal forge root for testing."""
    root = tmp_path / "forge"
    root.mkdir()
    (root / "registry").mkdir()
    (root / "registry" / "schemas").mkdir()
    (root / "packs").mkdir()
    (root / "scripts").mkdir()
    (root / "CLAUDE.md").write_text("# Forge Kernel\n", encoding="utf-8")
    return root


@pytest.fixture
def populated_forge_root(forge_root):
    """Forge root with minimal valid registries pre-populated."""
    # modules.json
    modules = {
        "version": "1.0",
        "layers": {
            "kernel": [{"id": "kernel.claude_md", "name": "CLAUDE.md", "path": "CLAUDE.md"}],
            "behaviors": [{"id": "behavior.review", "name": "review", "path": "behaviors/review.md"}],
            "domains": [{"id": "domain.java", "name": "java", "path": "domains/java.md"}],
            "templates": [{"id": "template.review_report", "name": "review-report", "path": "templates/review-report.md"}],
            "checklists": [{"id": "checklist.general_quality", "name": "general-quality", "path": "checklists/general-quality.md"}],
            "reports": [{"id": "report.task", "name": "task-report", "path": "reports/task-report.md"}],
        },
    }
    (forge_root / "registry" / "modules.json").write_text(
        json.dumps(modules, ensure_ascii=False), encoding="utf-8"
    )

    # skills.json
    skills = {
        "version": "1.0",
        "skills": [
            {
                "id": "skill.code_review",
                "name": "code-review",
                "triggers": ["review", "code review", "帮我 review", "评审"],
                "behavior": "behavior.review",
                "workflow": "workflow.light_review",
                "template": "template.review_report",
                "domains": ["domain.java"],
                "checklists": ["checklist.general_quality"],
                "context": "fork",
            },
            {
                "id": "skill.debug",
                "name": "debug",
                "triggers": ["debug", "排查", "定位", "root cause"],
                "behavior": "behavior.debug",
                "workflow": "workflow.debug_analysis",
                "template": "template.debug_report",
                "domains": [],
                "checklists": [],
                "context": "fork",
            },
            {
                "id": "skill.explore",
                "name": "explore",
                "triggers": ["先看看", "摸清楚", "先摸清楚", "explore"],
                "behavior": None,
                "workflow": "workflow.blocked_task",
                "template": "template.exploration",
                "domains": [],
                "checklists": [],
                "context": "inherit",
            },
        ],
    }
    (forge_root / "registry" / "skills.json").write_text(
        json.dumps(skills, ensure_ascii=False), encoding="utf-8"
    )

    # behaviors.json
    behaviors = {
        "behaviors": [
            {"id": "behavior.review", "name": "review"},
            {"id": "behavior.debug", "name": "debug"},
        ],
    }
    (forge_root / "registry" / "behaviors.json").write_text(
        json.dumps(behaviors, ensure_ascii=False), encoding="utf-8"
    )

    # domains.json
    domains = {
        "domains": [
            {"id": "domain.java", "name": "java"},
            {"id": "domain.spring", "name": "spring"},
        ],
    }
    (forge_root / "registry" / "domains.json").write_text(
        json.dumps(domains, ensure_ascii=False), encoding="utf-8"
    )

    # templates.json
    templates = {
        "templates": [
            {"id": "template.review_report", "name": "review-report"},
            {"id": "template.debug_report", "name": "debug-report"},
            {"id": "template.exploration", "name": "exploration"},
        ],
    }
    (forge_root / "registry" / "templates.json").write_text(
        json.dumps(templates, ensure_ascii=False), encoding="utf-8"
    )

    # checklists.json
    checklists = {
        "checklists": [
            {"id": "checklist.general_quality", "name": "general-quality"},
        ],
    }
    (forge_root / "registry" / "checklists.json").write_text(
        json.dumps(checklists, ensure_ascii=False), encoding="utf-8"
    )

    # reports.json
    reports = {
        "reports": [
            {"id": "report.task", "name": "task-report"},
        ],
    }
    (forge_root / "registry" / "reports.json").write_text(
        json.dumps(reports, ensure_ascii=False), encoding="utf-8"
    )

    # workflows.json
    workflows = {
        "workflows": [
            {"id": "workflow.light_review", "name": "light-review"},
            {"id": "workflow.debug_analysis", "name": "debug-analysis"},
            {"id": "workflow.blocked_task", "name": "blocked-task"},
        ],
    }
    (forge_root / "registry" / "workflows.json").write_text(
        json.dumps(workflows, ensure_ascii=False), encoding="utf-8"
    )

    # compositions.json (empty)
    (forge_root / "registry" / "compositions.json").write_text(
        json.dumps({"compositions": []}, ensure_ascii=False), encoding="utf-8"
    )

    # packs.json (index)
    (forge_root / "registry" / "packs.json").write_text(
        json.dumps({"packs": []}, ensure_ascii=False), encoding="utf-8"
    )

    # project.json
    project = {"name": "forge", "version": "1.1.1"}
    (forge_root / "registry" / "project.json").write_text(
        json.dumps(project, ensure_ascii=False), encoding="utf-8"
    )

    # skill-routing.json
    routing = {
        "version": "1.0",
        "keyword_sets": {},
        "generic_trigger_penalties": {},
        "skill_bias_rules": {},
        "tie_break_rules": [],
    }
    (forge_root / "registry" / "skill-routing.json").write_text(
        json.dumps(routing, ensure_ascii=False), encoding="utf-8"
    )

    # Create a schema file for skills.json
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "skills": {
                "type": "array",
                "items": {"type": "object"},
            },
        },
    }
    (forge_root / "registry" / "schemas" / "skills.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8"
    )

    # Create a sample pack file
    pack = {
        "id": "pack.test_pack",
        "name": "Test Pack",
        "purpose": "Test pack for unit tests",
        "behavior": "behavior.review",
        "workflow": "workflow.light_review",
        "template": "template.review_report",
        "domains": ["domain.java"],
        "checklists": ["checklist.general_quality"],
        "routing": {
            "preferred_skill": "skill.code_review",
            "keywords_any": ["spring", "review"],
            "keywords_all_groups": [["spring"]],
            "score_bonus": 10,
        },
    }
    (forge_root / "packs" / "test-pack.json").write_text(
        json.dumps(pack, ensure_ascii=False), encoding="utf-8"
    )

    return forge_root


@pytest.fixture
def mock_ctx():
    """Mock Click context object."""
    class MockCtx:
        obj = {"root": None, "verbose": False, "format": "text"}
    return MockCtx()


@pytest.fixture(autouse=True)
def add_forge_cli_to_path():
    """Make forge_cli importable in tests WITHOUT pip install.

    NOTE: this masks the fact that forge_cli is not importable from the repo
    root in production (no package install, relies on __main__.py + cwd).
    Tests passing does NOT mean `python -m forge_cli` works end-to-end;
    verify that separately (the C1 fix + __main__.py address the runtime path,
    but this fixture is still required for the test-time import).
    """
    forge_cli_path = Path(__file__).resolve().parents[1]
    path_str = str(forge_cli_path)
    added = path_str not in sys.path
    if added:
        sys.path.insert(0, path_str)
    yield
    # Restore sys.path so the injection does not leak across the whole session
    # (which previously masked packaging/import issues in other test modules).
    if added:
        try:
            sys.path.remove(path_str)
        except ValueError:
            pass
