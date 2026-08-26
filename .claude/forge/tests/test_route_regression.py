# -*- coding: utf-8 -*-
"""Tests for route/recommend regression corpus evaluation helpers."""

from forge_cli.route_regression import evaluate_regression_case, summarize_regression_results


def _case(expected):
    return {
        "id": "case.example",
        "category": "confidence_calibration",
        "mode": "route",
        "input": "example",
        "expected": expected,
    }


def test_evaluator_accepts_nullable_selection_and_declared_diagnostics():
    case = _case({
        "matched": False,
        "skill": None,
        "pack": None,
        "confidence": {"min": "low", "max": "low"},
        "diagnostics": {"selection_mode": "unmatched", "candidate_count": 0},
    })
    result = {
        "matched": False,
        "confidence": "low",
        "confidence_diagnostics": {"selection_mode": "unmatched", "candidate_count": 0},
    }

    evaluation = evaluate_regression_case(case, result)

    assert evaluation["passed"] is True


def test_evaluator_reports_declared_diagnostic_mismatch():
    case = _case({
        "matched": True,
        "skill": "skill.code_review",
        "pack": None,
        "confidence": {"min": "low", "max": "low"},
        "diagnostics": {"selection_mode": "prefer_fallback"},
    })
    result = {
        "matched": True,
        "confidence": "low",
        "skill": {"id": "skill.code_review"},
        "confidence_diagnostics": {"selection_mode": "ordinary"},
    }

    evaluation = evaluate_regression_case(case, result)

    assert evaluation["passed"] is False
    assert "Expected diagnostics.selection_mode=prefer_fallback, actual=ordinary" in evaluation["errors"]


def test_summary_groups_categories_modes_and_confidence():
    evaluations = [
        {"passed": True, "category": "no_match", "mode": "route", "actual": {"confidence": "low"}},
        {"passed": False, "category": "confidence_calibration", "mode": "recommend", "actual": {"confidence": "medium"}},
    ]

    summary = summarize_regression_results(evaluations)

    assert summary["total"] == {"passed": 1, "failed": 1, "total": 2}
    assert summary["by_category"]["no_match"]["passed"] == 1
    assert summary["by_mode"]["recommend"]["failed"] == 1
    assert summary["confidence_distribution"] == {"low": 1, "medium": 1}
