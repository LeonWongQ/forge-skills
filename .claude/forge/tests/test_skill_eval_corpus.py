"""Tests for repository-wide Skill behavior corpus coverage."""

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check-skill-eval-corpus.py"
SPEC = importlib.util.spec_from_file_location("check_skill_eval_corpus", SCRIPT_PATH)
check_skill_eval_corpus = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_skill_eval_corpus)


def _case(case_id: str, category: str) -> dict:
    return {
        "id": case_id,
        "skill": "alpha",
        "category": category,
        "execution": {
            "fixture": "empty",
            "sandbox": "read-only",
            "timeout_seconds": 60,
            "mode": "automated",
            "requires_capabilities": ["filesystem_read"],
        },
        "prompt": "Evaluate the requested behavior.",
        "hard_requirements": ["Preserve the task boundary.", "Ground conclusions in evidence."],
        "forbidden_behaviors": ["Invent unsupported facts."],
    }


def test_repository_corpus_requires_every_skill(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    for name in ("alpha", "beta"):
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test.\n---\n", encoding="utf-8")

    corpus = tmp_path / "skill-behavior-cases.json"
    categories = ("representative", "boundary", "known_failure", "adversarial")
    corpus.write_text(
        json.dumps({
            "version": 1,
            "cases": [_case(f"skill-eval.alpha.case-{index}", category) for index, category in enumerate(categories)],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(check_skill_eval_corpus, "CORPUS_PATH", corpus)
    monkeypatch.setattr(check_skill_eval_corpus, "REQUIRED_RISK_SKILLS", set())

    issues = check_skill_eval_corpus.validate_corpus(corpus, skills)

    assert "repository corpus must cover every Skill; missing: beta" in issues
