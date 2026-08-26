# -*- coding: utf-8 -*-
"""Stable diagnostic-report contract normalization and comparison."""

from typing import Any, Dict, List, Optional, Tuple


SUMMARY_FIELDS = ("ok", "total_checks", "warning_count", "error_count", "strict")
MESSAGE_FIELDS = ("level", "code", "message", "details")


def _require_mapping(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    return value


def canonical_report_contract(report: Any, expected_command: Optional[str] = None) -> Dict[str, Any]:
    """Return the stable portion of a validate/doctor report.

    Execution timing and the machine-specific root are intentionally excluded.
    All selected check and diagnostic content remains ordered and contractual.
    """
    payload = _require_mapping(report, "report")
    command = payload.get("command")
    if not isinstance(command, str) or not command:
        raise ValueError("report.command must be a non-empty string")
    if expected_command is not None and command != expected_command:
        raise ValueError(f"report.command={command!r}, expected {expected_command!r}")

    summary = _require_mapping(payload.get("summary"), "report.summary")
    normalized_summary = {}
    for field in SUMMARY_FIELDS:
        if field not in summary:
            raise ValueError(f"report.summary.{field} is required")
        normalized_summary[field] = summary[field]

    normalized_checks = []
    for check_index, check in enumerate(_require_list(payload.get("checks"), "report.checks")):
        check_data = _require_mapping(check, f"report.checks[{check_index}]")
        name = check_data.get("name")
        passed = check_data.get("passed")
        if not isinstance(name, str) or not name:
            raise ValueError(f"report.checks[{check_index}].name must be a non-empty string")
        if not isinstance(passed, bool):
            raise ValueError(f"report.checks[{check_index}].passed must be a boolean")

        normalized_messages = []
        for message_index, message in enumerate(
            _require_list(check_data.get("messages"), f"report.checks[{check_index}].messages")
        ):
            message_data = _require_mapping(
                message, f"report.checks[{check_index}].messages[{message_index}]"
            )
            normalized_message = {}
            for field in MESSAGE_FIELDS:
                if field not in message_data:
                    raise ValueError(
                        f"report.checks[{check_index}].messages[{message_index}].{field} is required"
                    )
                normalized_message[field] = message_data[field]
            normalized_messages.append(normalized_message)

        normalized_checks.append({"name": name, "passed": passed, "messages": normalized_messages})

    return {"command": command, "summary": normalized_summary, "checks": normalized_checks}


def first_contract_difference(expected: Any, actual: Any, path: str = "") -> Optional[Tuple[str, Any, Any]]:
    """Return the first ordered difference as ``(path, expected, actual)``."""
    if type(expected) is not type(actual):
        return path or "report", expected, actual
    if isinstance(expected, dict):
        for key in expected:
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                return child_path, expected[key], None
            difference = first_contract_difference(expected[key], actual[key], child_path)
            if difference:
                return difference
        for key in actual:
            if key not in expected:
                child_path = f"{path}.{key}" if path else key
                return child_path, None, actual[key]
        return None
    if isinstance(expected, list):
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            difference = first_contract_difference(expected_item, actual_item, f"{path}[{index}]")
            if difference:
                return difference
        if len(expected) != len(actual):
            index = min(len(expected), len(actual))
            return f"{path}[{index}]", (
                expected[index] if index < len(expected) else None
            ), (actual[index] if index < len(actual) else None)
        return None
    if expected != actual:
        return path or "report", expected, actual
    return None
