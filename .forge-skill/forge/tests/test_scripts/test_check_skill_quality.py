# -*- coding: utf-8 -*-
"""Tests for the repository skill quality gate."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check-skill-quality.py"
SPEC = importlib.util.spec_from_file_location("check_skill_quality", SCRIPT_PATH)
check_skill_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_skill_quality)


def _write_skill(tmp_path: Path, prompt: str = "Use $sample-skill to handle this task.") -> Path:
    skill_dir = tmp_path / "sample-skill"
    (skill_dir / "agents").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        """---
name: sample-skill
description: Handle a representative task safely and reliably.
---

# Sample Skill

Read [the guide](references/guide.md) before acting.
""",
        encoding="utf-8",
    )
    (skill_dir / "agents" / "openai.yaml").write_text(
        f'''interface:
  display_name: "Sample Skill"
  short_description: "Handle representative tasks safely and reliably."
  default_prompt: "{prompt}"
''',
        encoding="utf-8",
    )
    return skill_dir


def test_valid_skill_passes(tmp_path):
    assert check_skill_quality.validate_skill(_write_skill(tmp_path)) == []


def test_default_prompt_must_name_the_skill(tmp_path):
    errors = check_skill_quality.validate_skill(
        _write_skill(tmp_path, prompt="Handle this task safely.")
    )

    assert any("default_prompt must explicitly mention $sample-skill" in error for error in errors)


def test_missing_local_file_is_reported(tmp_path):
    skill_dir = _write_skill(tmp_path)
    (skill_dir / "references" / "guide.md").unlink()

    errors = check_skill_quality.validate_skill(skill_dir)

    assert any("referenced local path does not exist: references/guide.md" in error for error in errors)


def test_explanatory_body_must_be_english(tmp_path):
    skill_dir = _write_skill(tmp_path)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\n这是中文说明。\n", encoding="utf-8")

    errors = check_skill_quality.validate_skill(skill_dir)

    assert any("explanatory body must be English" in error for error in errors)


def test_frontmatter_may_contain_cjk_trigger_keywords(tmp_path):
    skill_dir = _write_skill(tmp_path)
    skill_path = skill_dir / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8").replace(
        "description: Handle a representative task safely and reliably.",
        "description: Handle a representative task safely. Triggers include 检查 and 审查.",
    )
    skill_path.write_text(content, encoding="utf-8")

    assert check_skill_quality.validate_skill(skill_dir) == []


def test_registry_coverage_reports_unregistered_and_missing_skill_dirs(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    (skills_root / "registered").mkdir(parents=True)
    (skills_root / "unregistered").mkdir()
    registry = tmp_path / "skills.json"
    registry.write_text('{"skills":[{"name":"registered"},{"name":"missing"}]}', encoding="utf-8")
    monkeypatch.setattr(check_skill_quality, "SKILLS_REGISTRY", registry)

    errors = check_skill_quality.validate_registry_coverage(list(skills_root.iterdir()))

    assert "skills registry: unregistered skill directory: unregistered" in errors
    assert "skills registry: registered skill directory is missing: missing" in errors


def test_implement_skill_retains_effectful_retry_safety_contract():
    implement_skill = check_skill_quality.SKILLS_ROOT / "implement" / "SKILL.md"
    content = implement_skill.read_text(encoding="utf-8")

    assert "the failure is guaranteed to occur before commit" in content
    assert "idempotent for the same request or idempotency key" in content
    assert "duplicate effects are detected or compensated transactionally" in content
    assert "A call-count assertion is not proof against duplicate committed effects" in content
    assert "no duplicate committed effect" in content
