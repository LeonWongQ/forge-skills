# -*- coding: utf-8 -*-
"""Tests for forge_cli.result_builders — message and check result factories."""

from forge_cli.result_builders import (
    add_msg,
    finalize_check_result,
    make_check_result,
    make_message,
    summarize_checks,
)


class TestMakeMessage:
    def test_basic_message(self):
        msg = make_message("info", "TEST_CODE", "test message")
        assert msg["level"] == "info"
        assert msg["code"] == "TEST_CODE"
        assert msg["message"] == "test message"
        assert msg["details"] is None

    def test_with_details(self):
        msg = make_message("error", "ERR", "failed", {"key": "val"})
        assert msg["details"] == {"key": "val"}


class TestMakeCheckResult:
    def test_default_state(self):
        result = make_check_result("test-check")
        assert result["name"] == "test-check"
        assert result["passed"] is True
        assert result["duration_ms"] == 0
        assert result["messages"] == []

    def test_failed_state(self):
        result = make_check_result("test-check", passed=False)
        assert result["passed"] is False


class TestFinalizeCheckResult:
    def test_adds_duration(self):
        result = make_check_result("test")
        finalized = finalize_check_result(result, 100.0)
        assert finalized["duration_ms"] > 0


class TestAddMsg:
    def test_appends_message(self):
        result = make_check_result("test")
        add_msg(result, "error", "ERR_CODE", "Something failed")
        assert len(result["messages"]) == 1
        assert result["messages"][0]["code"] == "ERR_CODE"


class TestSummarizeChecks:
    def test_all_passed(self):
        checks = [
            {"name": "c1", "passed": True, "messages": []},
            {"name": "c2", "passed": True, "messages": []},
        ]
        summary = summarize_checks(checks)
        assert summary["ok"] is True
        assert summary["error_count"] == 0
        assert summary["warning_count"] == 0

    def test_one_failed(self):
        checks = [
            {"name": "c1", "passed": True, "messages": []},
            {"name": "c2", "passed": False, "messages": [
                {"level": "error", "code": "ERR", "message": "failed"}
            ]},
        ]
        summary = summarize_checks(checks)
        assert summary["ok"] is False
        assert summary["error_count"] == 1

    def test_strict_mode_warnings_fail(self):
        checks = [
            {"name": "c1", "passed": True, "messages": [
                {"level": "warning", "code": "WARN", "message": "be careful"}
            ]},
        ]
        summary = summarize_checks(checks, strict=True)
        assert summary["ok"] is False
        assert summary["warning_count"] == 1

    def test_non_strict_warnings_pass(self):
        checks = [
            {"name": "c1", "passed": True, "messages": [
                {"level": "warning", "code": "WARN", "message": "be careful"}
            ]},
        ]
        summary = summarize_checks(checks, strict=False)
        assert summary["ok"] is True
