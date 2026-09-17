"""Phase 9 minimum case coverage for supported Skills."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evals" / "skill-behavior-cases.json"
REQUIRED_CATEGORIES = {"representative", "boundary", "adversarial"}
MIN_CASES = 3
SUPPORTED_SKILLS = ("code-review", "debug", "plan", "explain", "explore")


def _compatible(case: dict, skill: str) -> bool:
    execution = case.get("execution", {})
    return (
        case.get("skill") == skill
        and execution.get("mode") == "automated"
        and execution.get("sandbox") == "read-only"
        and set(execution.get("requires_capabilities", [])) <= {"filesystem_read"}
    )


def test_supported_skills_have_phase9_case_coverage():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = corpus["cases"]

    duplicate_ids = [case_id for case_id in {
        case.get("id") for case in cases
    } if case_id is not None and sum(item.get("id") == case_id for item in cases) > 1]
    assert not duplicate_ids, f"duplicate evaluation case ids: {sorted(duplicate_ids)}"

    failures = {}
    for skill in SUPPORTED_SKILLS:
        matching = [case for case in cases if _compatible(case, skill)]
        categories = {case.get("category") for case in matching}
        if len(matching) < MIN_CASES or not REQUIRED_CATEGORIES <= categories:
            failures[skill] = {
                "caseCount": len(matching),
                "categories": sorted(category for category in categories if category),
            }

    assert not failures, f"Phase 9 case coverage is incomplete: {failures}"
