# -*- coding: utf-8 -*-
"""Tests for diagnostic report contract normalization and freshness checks."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

from forge_cli.report_contract import canonical_report_contract, first_contract_difference


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check-report-freshness.py"
SPEC = importlib.util.spec_from_file_location("check_report_freshness", SCRIPT_PATH)
check_report_freshness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_report_freshness)


def _report(command: str = "validate") -> dict:
    return {
        "command": command,
        "root": "D:/machine-a/forge",
        "checks": [
            {
                "name": "registry",
                "passed": True,
                "duration_ms": 12,
                "messages": [
                    {
                        "level": "info",
                        "code": "SCHEMA_VALID",
                        "message": "registry is valid",
                        "details": None,
                    }
                ],
            }
        ],
        "summary": {
            "ok": True,
            "warning_count": 0,
            "error_count": 0,
            "strict": False,
            "total_checks": 1,
        },
    }


def _write_report(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report), encoding="utf-8")


def test_canonical_contract_ignores_root_and_duration():
    committed = _report()
    fresh = deepcopy(committed)
    fresh["root"] = "D:/machine-b/forge"
    fresh["checks"][0]["duration_ms"] = 99

    assert first_contract_difference(
        canonical_report_contract(committed, "validate"),
        canonical_report_contract(fresh, "validate"),
    ) is None


def test_canonical_contract_detects_summary_and_message_drift():
    committed = canonical_report_contract(_report(), "validate")
    fresh = canonical_report_contract(_report(), "validate")
    fresh["summary"]["total_checks"] = 7

    assert first_contract_difference(committed, fresh)[0] == "summary.total_checks"

    fresh = canonical_report_contract(_report(), "validate")
    fresh["checks"][0]["messages"][0]["code"] = "CHANGED"
    assert first_contract_difference(committed, fresh)[0] == "checks[0].messages[0].code"


def test_canonical_contract_rejects_malformed_payloads():
    malformed = _report()
    del malformed["checks"][0]["messages"][0]["details"]

    try:
        canonical_report_contract(malformed, "validate")
    except ValueError as error:
        assert "details is required" in str(error)
    else:
        raise AssertionError("expected malformed report to fail")


def test_freshness_script_detects_contract_drift(tmp_path, monkeypatch, capsys):
    committed = _report()
    fresh = _report()
    fresh["summary"]["total_checks"] = 7
    _write_report(tmp_path / "validate-report.json", committed)
    _write_report(tmp_path / "validate-report.fresh.json", fresh)
    monkeypatch.setattr(check_report_freshness, "OUT_DIR", tmp_path)
    monkeypatch.setattr(check_report_freshness, "REPORT_NAMES", ("validate",))
    monkeypatch.setattr(check_report_freshness, "EXPECTED_CHECK_NAMES", {"validate": ["registry"]})

    assert check_report_freshness.main() == 1
    assert "summary.total_checks differs" in capsys.readouterr().out


def test_freshness_script_accepts_semantically_equal_reports(tmp_path, monkeypatch):
    committed = _report()
    fresh = _report()
    fresh["root"] = "D:/machine-b/forge"
    fresh["checks"][0]["duration_ms"] = 99
    _write_report(tmp_path / "validate-report.json", committed)
    _write_report(tmp_path / "validate-report.fresh.json", fresh)
    monkeypatch.setattr(check_report_freshness, "OUT_DIR", tmp_path)
    monkeypatch.setattr(check_report_freshness, "REPORT_NAMES", ("validate",))
    monkeypatch.setattr(check_report_freshness, "EXPECTED_CHECK_NAMES", {"validate": ["registry"]})

    assert check_report_freshness.main() == 0


def test_freshness_script_fails_for_missing_fresh_report(tmp_path, monkeypatch):
    _write_report(tmp_path / "doctor-report.json", _report("doctor"))
    monkeypatch.setattr(check_report_freshness, "OUT_DIR", tmp_path)
    monkeypatch.setattr(check_report_freshness, "REPORT_NAMES", ("doctor",))
    monkeypatch.setattr(check_report_freshness, "EXPECTED_CHECK_NAMES", {"doctor": ["registry"]})

    assert check_report_freshness.main() == 1
