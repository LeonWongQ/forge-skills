# -*- coding: utf-8 -*-
"""Process-level smoke tests for `python -m forge_cli`."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_python_m_forge_cli_version_json(populated_forge_root):
    package_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) if not existing else os.pathsep.join([str(package_root), existing])

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "forge_cli",
            "--root",
            str(populated_forge_root),
            "--format",
            "json",
            "version",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(populated_forge_root.parent),
        env=env,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["name"] == "forge"
    assert payload["version"] == "1.1.1"


def test_python_m_forge_cli_route_json_uses_real_registry():
    package_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) if not existing else os.pathsep.join([str(package_root), existing])

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "forge_cli",
            "--root",
            str(package_root),
            "--format",
            "json",
            "route",
            "帮我 review 一个 spring service 改动",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(package_root),
        env=env,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["matched"] is True
    assert payload["skill"]["id"] == "skill.code_review"


def test_python_m_forge_cli_resolve_json_uses_real_registry(tmp_path):
    package_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) if not existing else os.pathsep.join([str(package_root), existing])

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "forge_cli",
            "--root",
            str(package_root),
            "--format",
            "json",
            "resolve",
            "帮我 review 一个 spring service 改动",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(tmp_path),
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "1.0"
    assert payload["selection"]["skill"] == "skill.code_review"
    assert payload["resolution"]["ok"] is True
