# -*- coding: utf-8 -*-
"""Tests for quick/full local quality gate selection."""

import importlib.util
from pathlib import Path

import pytest
import yaml


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run-local-checks.py"
REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("run_local_checks", SCRIPT_PATH)
run_local_checks = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_local_checks)


def test_quick_gate_contains_only_fast_deterministic_checks():
    steps = run_local_checks.build_steps("quick")

    assert [label for label, _ in steps] == [
        "text integrity", "sensitive content", "skill quality", "skill eval corpus", "validate"
    ]


def test_full_gate_preserves_regressions_and_pytest():
    steps = run_local_checks.build_steps("full", "D:/tmp/forge-pytest")

    assert [label for label, _ in steps] == [
        "text integrity",
        "sensitive content",
        "skill quality",
        "skill eval corpus",
        "validate",
        "route regression",
        "documentation facts",
        "pytest",
    ]
    assert steps[-1][1][-2:] == ["--basetemp", "D:/tmp/forge-pytest"]


def test_full_gate_requires_an_isolated_pytest_directory():
    with pytest.raises(ValueError, match="pytest_temp is required"):
        run_local_checks.build_steps("full")


def test_unknown_gate_mode_is_rejected():
    with pytest.raises(ValueError, match="unsupported quality gate mode"):
        run_local_checks.build_steps("unknown")


def test_pre_commit_uses_the_quick_gate():
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    hook = next(item for item in hooks if item["id"] == "forge-local-quality-gate")

    assert hook["entry"].endswith("run-local-checks.py --quick")


def test_platform_wrappers_forward_mode_arguments():
    scripts_dir = SCRIPT_PATH.parent

    assert "%*" in (scripts_dir / "run-local-checks.bat").read_text(encoding="utf-8")
    assert '"$@"' in (scripts_dir / "run-local-checks.sh").read_text(encoding="utf-8")


def test_ci_runs_full_deterministic_gate_without_llm_evaluation():
    workflow = (REPO_ROOT / ".github" / "workflows" / "quality-gate.yml").read_text(encoding="utf-8")

    assert "run-local-checks.py --full" in workflow
    assert 'node-version: "22"' in workflow
    assert "npm ci --ignore-scripts --no-audit --no-fund" in workflow
    assert "playwright install" not in workflow
    assert "run-skill-evals.py" not in workflow
    assert "confirm-llm-evaluation" not in workflow
    assert "windows-latest" in workflow
    assert "ubuntu-latest" in workflow
    assert "macos-latest" in workflow
    assert "matrix.os" in workflow
