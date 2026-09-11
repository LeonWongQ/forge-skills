# -*- coding: utf-8 -*-
"""Tests for read-only deployment verification aggregation."""

import os
import subprocess
import sys
from pathlib import Path

from forge_cli.deployment_verification import LinkInspection, expected_links, verify_deployment


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _run_source_verifier(project, tool, source):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PACKAGE_ROOT) if not existing else os.pathsep.join([str(PACKAGE_ROOT), existing])
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "forge_cli.deployment_verify",
            "--project",
            str(project),
            "--tool",
            tool,
            "--source-root",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(PACKAGE_ROOT),
        env=env,
    )


class FakeInspector:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def inspect(self, path):
        self.calls.append(path)
        return self.values[path.name]


def _source(tmp_path):
    source = tmp_path / "source" / ".claude"
    for name in ("forge", "skills", "rules", "forge-data"):
        (source / name).mkdir(parents=True, exist_ok=True)
    return source


def test_expected_links_match_all_tool_layouts(tmp_path):
    source = _source(tmp_path)
    project = tmp_path / "project"

    assert [item["path"].relative_to(project).as_posix() for item in expected_links(project, "claude", source)] == [".claude/forge", ".claude/skills", ".claude/forge-data"]
    assert [item["path"].relative_to(project).as_posix() for item in expected_links(project, "cursor", source)] == [".cursor/forge", ".cursor/skills", ".cursor/forge-data", ".cursor/rules"]
    assert [item["path"].relative_to(project).as_posix() for item in expected_links(project, "codex", source)] == [".codex/forge", ".codex/skills", ".codex/forge-data", ".codex/rules"]


def test_valid_deployment_matches_all_expected_junctions(tmp_path):
    source = _source(tmp_path)
    project = tmp_path / "project"
    inspector = FakeInspector({"forge": LinkInspection("junction", source / "forge"), "skills": LinkInspection("junction", source / "skills"), "forge-data": LinkInspection("junction", source / "forge-data")})

    result = verify_deployment(project, "claude", source, inspector, platform="win32")

    assert result["ok"] is True
    assert result["summary"] == {"verified": 3, "failed": 0, "skipped": 0}
    assert len(inspector.calls) == 3


def test_wrong_target_and_real_directory_fail_without_inspector_mutation(tmp_path):
    source = _source(tmp_path)
    project = tmp_path / "project"
    before = source.stat().st_mtime_ns
    inspector = FakeInspector({"forge": LinkInspection("directory"), "skills": LinkInspection("junction", tmp_path / "other" / "skills"), "forge-data": LinkInspection("junction", source / "forge-data")})

    result = verify_deployment(project, "claude", source, inspector, platform="win32")

    assert result["ok"] is False
    assert [item["code"] for item in result["items"]] == ["LINK_NOT_REPARSE_POINT", "JUNCTION_TARGET_MISMATCH", "JUNCTION_TARGET_MATCH"]
    assert source.stat().st_mtime_ns == before


def test_cursor_skips_rules_when_source_rules_are_absent(tmp_path):
    source = _source(tmp_path)
    (source / "rules").rmdir()
    project = tmp_path / "project"
    inspector = FakeInspector({"forge": LinkInspection("junction", source / "forge"), "skills": LinkInspection("junction", source / "skills"), "forge-data": LinkInspection("junction", source / "forge-data")})

    result = verify_deployment(project, "cursor", source, inspector, platform="win32")

    assert result["ok"] is True
    assert result["items"][-1]["code"] == "RULES_SOURCE_ABSENT"
    assert result["summary"]["skipped"] == 1


def test_non_windows_reports_unsupported_without_inspection(tmp_path):
    source = _source(tmp_path)
    inspector = FakeInspector({})

    result = verify_deployment(tmp_path / "project", "claude", source, inspector, platform="linux")

    assert result["environment_error"] == "JUNCTION_INSPECTION_UNSUPPORTED"
    assert inspector.calls == []


def test_codex_skips_rules_when_source_rules_are_absent(tmp_path):
    source = _source(tmp_path)
    (source / "rules").rmdir()
    project = tmp_path / "project"
    inspector = FakeInspector({"forge": LinkInspection("junction", source / "forge"), "skills": LinkInspection("junction", source / "skills"), "forge-data": LinkInspection("junction", source / "forge-data")})

    result = verify_deployment(project, "codex", source, inspector, platform="win32")

    assert result["ok"] is True
    assert result["items"][-1]["code"] == "RULES_SOURCE_ABSENT"
    assert result["summary"]["skipped"] == 1


def test_source_verifier_runs_without_package_install(tmp_path):
    source = _source(tmp_path)
    project = tmp_path / "project with spaces"

    proc = _run_source_verifier(project, "claude", source)

    assert proc.returncode == 1
    assert f"Project: {project.resolve()}" in proc.stdout
    assert f"Source: {source.resolve()}" in proc.stdout
    assert "[FAIL] forge LINK_MISSING" in proc.stdout
    assert "[FAIL] skills LINK_MISSING" in proc.stdout


def test_source_verifier_rejects_invalid_tool_without_package_install(tmp_path):
    source = _source(tmp_path)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PACKAGE_ROOT) if not existing else os.pathsep.join([str(PACKAGE_ROOT), existing])

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "forge_cli.deployment_verify",
            "--project",
            str(tmp_path / "project"),
            "--tool",
            "unknown",
            "--source-root",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(PACKAGE_ROOT),
        env=env,
    )

    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_link_script_launches_utf8_python_installer():
    link_script = PACKAGE_ROOT.parents[1] / "install-link-forge.bat"
    content = link_script.read_text(encoding="utf-8")

    assert "PYTHONUTF8=1" in content
    assert "PYTHONIOENCODING=utf-8" in content
    assert "-m forge_cli.link_installer %*" in content
    assert "LINK_ARGS" not in content
    assert "--link-spec" not in content
    assert "mklink" not in content
    assert "Python 3.11" in content
