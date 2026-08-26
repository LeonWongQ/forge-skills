# -*- coding: utf-8 -*-
"""Read-only personal Claude Code SessionStart advisory for Forge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .helpers import TOOL_CONFIG_DIRECTORIES
from .personal_hook_state import list_manifests
from .runtime_paths import migrate_legacy_runtime_directory, project_runtime_directory

ADVISORY = (
    "检测到当前项目存在可恢复的 Forge Runtime 任务。请先询问用户："
    "恢复一个已有任务，还是开始新任务。开始新任务不得修改、删除或归档已有任务。"
)


def _project_directory(event: Any) -> Path | None:
    if isinstance(event, dict) and isinstance(event.get("cwd"), str) and event["cwd"].strip():
        return Path(event["cwd"])
    configured = os.environ.get("CLAUDE_PROJECT_DIR")
    if configured:
        return Path(configured)
    return None


def _configured_tool(project: Path) -> str:
    """Use the recorded deployment tool, retaining Claude for old installs."""
    configured = os.environ.get("FORGE_TOOL", "").casefold()
    if configured in TOOL_CONFIG_DIRECTORIES:
        return configured
    project_key = os.path.normcase(str(project.resolve()))
    matching = [
        item.get("tool")
        for item in list_manifests()
        if os.path.normcase(str(item.get("project", ""))) == project_key
        and item.get("tool") in TOOL_CONFIG_DIRECTORIES
        and item.get("status") == "installed"
    ]
    return matching[0] if len(set(matching)) == 1 else "claude"


def _forge_root(project: Path, tool: str = "claude") -> Path | None:
    candidate = project / TOOL_CONFIG_DIRECTORIES[tool] / "forge"
    if not (candidate / "forge_cli").is_dir() or not (candidate / "registry" / "modules.json").is_file():
        return None
    return candidate.resolve()


def _discover(forge_root: Path, directory: Path) -> bool:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "forge_cli",
                "--root",
                str(forge_root),
                "--format",
                "json",
                "runtime-list-paused",
                "--directory",
                str(directory),
            ],
            cwd=str(forge_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
        if completed.returncode:
            return False
        result = json.loads(completed.stdout)
        return isinstance(result, dict) and isinstance(result.get("candidates"), list) and bool(result["candidates"])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def main(stdin: Any = sys.stdin, stdout: Any = sys.stdout) -> int:
    try:
        event = json.load(stdin)
        project = _project_directory(event)
        if project is None or not project.is_dir():
            return 0
        migrate_legacy_runtime_directory(project.resolve())
        runtime_directory = project_runtime_directory(project.resolve())
        if not runtime_directory.is_dir():
            return 0
        forge_root = _forge_root(project.resolve(), _configured_tool(project))
        if forge_root is None or not _discover(forge_root, runtime_directory):
            return 0
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": ADVISORY,
                }
            },
            stdout,
            ensure_ascii=False,
        )
        stdout.write("\n")
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
