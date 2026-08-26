"""Tests for the LLM Skill evaluation runner."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run-skill-evals.py"
SPEC = importlib.util.spec_from_file_location("run_skill_evals", SCRIPT_PATH)
run_skill_evals = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_skill_evals)


def test_timeout_multiplier_defaults_to_one():
    args = run_skill_evals.parse_args([])

    assert args.timeout_multiplier == 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf"])
def test_timeout_multiplier_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(SystemExit):
        run_skill_evals.parse_args(["--timeout-multiplier", value])


def test_timeout_multiplier_accepts_positive_finite_value():
    args = run_skill_evals.parse_args(["--timeout-multiplier", "2.5"])

    assert args.timeout_multiplier == 2.5


def test_successful_cli_with_sandbox_helper_failure_is_not_completed():
    status = run_skill_evals.classify_execution_status(
        0,
        "",
        "windows sandbox: orchestrator_helper_launch_failed",
    )

    assert status == "sandbox_unavailable"


def test_successful_cli_without_infrastructure_markers_is_unscored():
    assert run_skill_evals.classify_execution_status(0, "ok", "") == "completed_unscored"


def test_native_codex_requires_adjacent_windows_helper(tmp_path):
    command = tmp_path / "codex.exe"
    command.write_bytes(b"")

    issue = run_skill_evals.codex_windows_helper_issue(str(command), platform_name="nt")

    assert issue == "Codex Windows sandbox helper is missing beside the selected native CLI: codex-windows-sandbox-setup.exe"


def test_native_codex_accepts_adjacent_windows_helper(tmp_path):
    command = tmp_path / "codex.exe"
    command.write_bytes(b"")
    (tmp_path / "codex-windows-sandbox-setup.exe").write_bytes(b"")

    assert run_skill_evals.codex_windows_helper_issue(str(command), platform_name="nt") is None


def test_preflight_rejects_backend_command_with_broken_version_check(tmp_path, monkeypatch):
    command = tmp_path / "codex.cmd"
    command.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        run_skill_evals.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "broken"),
    )

    ready, messages = run_skill_evals.preflight("codex", str(command), ignore_user_config=True)

    assert ready is False
    assert messages[-1] == "Codex backend command health check exited with code 1."
