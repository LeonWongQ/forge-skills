# -*- coding: utf-8 -*-
"""Forge CLI — result builder utilities for check results and messages."""

from typing import Any, Dict, List

from .helpers import now_ms


def make_message(level: str, code: str, message: str, details: Any = None) -> Dict[str, Any]:
    return {
        "level": level,
        "code": code,
        "message": message,
        "details": details,
    }


def make_check_result(name: str, passed: bool = True) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "duration_ms": 0,
        "messages": [],
    }


def finalize_check_result(result: Dict[str, Any], start_ms: float) -> Dict[str, Any]:
    result["duration_ms"] = int(now_ms() - start_ms)
    return result


def add_msg(result: Dict[str, Any], level: str, code: str, message: str, details: Any = None):
    result["messages"].append(make_message(level, code, message, details))


def summarize_checks(checks: List[Dict[str, Any]], strict: bool = False) -> Dict[str, Any]:
    warning_count = 0
    error_count = 0
    all_passed = True

    for check in checks:
        if not check["passed"]:
            all_passed = False
        for m in check["messages"]:
            if m["level"] == "warning":
                warning_count += 1
            elif m["level"] == "error":
                error_count += 1

    ok = all_passed and (warning_count == 0 if strict else True)

    return {
        "ok": ok,
        "warning_count": warning_count,
        "error_count": error_count,
        "strict": strict,
        "total_checks": len(checks),
    }
