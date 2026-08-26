"""Tests for Skill entrypoint quality constraints."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check-skill-quality.py"
SPEC = importlib.util.spec_from_file_location("check_skill_quality", SCRIPT_PATH)
check_skill_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_skill_quality)


def _skill(root: Path, name: str, paragraph: str) -> Path:
    skill = root / name
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill.\n---\n\n# {name}\n\n{paragraph}\n",
        encoding="utf-8",
    )
    return skill


def test_duplicate_long_guidance_is_rejected(tmp_path):
    paragraph = " ".join(["Repeated decision guidance must live in one shared reference."] * 6)
    skills = [_skill(tmp_path, "alpha", paragraph), _skill(tmp_path, "beta", paragraph)]

    issues = check_skill_quality.validate_duplicate_paragraphs(skills)

    assert len(issues) == 1
    assert "alpha, beta" in issues[0]


def test_short_repeated_reminders_are_allowed(tmp_path):
    paragraph = "Keep the result scoped."
    skills = [_skill(tmp_path, "alpha", paragraph), _skill(tmp_path, "beta", paragraph)]

    assert check_skill_quality.validate_duplicate_paragraphs(skills) == []


def test_shared_reference_pointer_is_allowed(tmp_path):
    paragraph = (
        "Read [.claude/forge/references/shared.md](.claude/forge/references/shared.md) "
        + "when this conditional mode applies. " * 12
    )
    skills = [_skill(tmp_path, "alpha", paragraph), _skill(tmp_path, "beta", paragraph)]

    assert check_skill_quality.validate_duplicate_paragraphs(skills) == []
