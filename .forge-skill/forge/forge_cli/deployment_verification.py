# -*- coding: utf-8 -*-
"""Read-only verification for Windows Forge directory-junction deployments."""

import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


MOUNT_POINT_TAG = "0xa0000003"
TOOL_CONFIG = {"claude": ".claude", "cursor": ".cursor", "codex": ".codex"}


@dataclass(frozen=True)
class LinkInspection:
    kind: str
    target: Optional[Path] = None
    detail: Optional[str] = None


class LinkInspector(Protocol):
    def inspect(self, path: Path) -> LinkInspection: ...


def _normalized(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve(strict=False))))


def expected_links(project: Path, tool: str, source_claude: Path) -> List[Dict[str, Any]]:
    config = project / TOOL_CONFIG[tool]
    links = [
        {"name": "forge", "path": config / "forge", "source": source_claude / "forge", "required": True},
        {"name": "skills", "path": config / "skills", "source": source_claude / "skills", "required": True},
    ]
    if tool in ("cursor", "codex"):
        rules_source = source_claude / "rules"
        links.append({"name": "rules", "path": config / "rules", "source": rules_source, "required": rules_source.is_dir()})
    return links


def _junction_target(path: Path, target_text: str) -> Path:
    normalized = target_text.replace("/", "\\")
    for prefix in ("\\\\?\\", "\\??\\"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    target = Path(normalized)
    return target if target.is_absolute() else path.parent / target


class WindowsJunctionInspector:
    """Inspect only; never creates, repairs, or removes a filesystem entry."""

    def inspect(self, path: Path) -> LinkInspection:
        try:
            mode = os.lstat(path).st_mode
        except FileNotFoundError:
            return LinkInspection("missing")
        except OSError as error:
            return LinkInspection("unreadable", detail=str(error))
        if not hasattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT"):
            return LinkInspection("unsupported", detail="reparse attributes unavailable")
        attributes = os.lstat(path).st_file_attributes
        if not attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return LinkInspection("directory" if stat.S_ISDIR(mode) else "file")
        try:
            probe = subprocess.run(
                ["fsutil", "reparsepoint", "query", str(path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
        except OSError as error:
            return LinkInspection("unreadable", detail=str(error))
        output = (probe.stdout + probe.stderr).lower()
        if probe.returncode != 0:
            return LinkInspection("other_reparse", detail=output.strip())
        if MOUNT_POINT_TAG not in output:
            return LinkInspection("other_reparse", detail=output.strip())
        try:
            target_text = os.readlink(path)
        except OSError as error:
            return LinkInspection("unreadable", detail=str(error))
        target = _junction_target(path, target_text)
        return LinkInspection("junction", target=target)


def verify_deployment(project: Path, tool: str, source_claude: Path, inspector: Optional[LinkInspector] = None, platform: Optional[str] = None) -> Dict[str, Any]:
    platform = platform or sys.platform
    project = project.resolve(strict=False)
    source_claude = source_claude.resolve(strict=False)
    if platform != "win32":
        return {"command": "deployment-verify", "ok": False, "project": str(project), "tool": tool, "source_root": str(source_claude), "platform": platform, "items": [], "summary": {"verified": 0, "failed": 0, "skipped": 0}, "environment_error": "JUNCTION_INSPECTION_UNSUPPORTED"}
    inspector = inspector or WindowsJunctionInspector()
    items = []
    for link in expected_links(project, tool, source_claude):
        source = link["source"]
        if not link["required"]:
            status, code, actual = "skip", "RULES_SOURCE_ABSENT", None
        elif not source.is_dir():
            status, code, actual = "fail", "SOURCE_MISSING", None
        else:
            inspected = inspector.inspect(link["path"])
            actual = str(inspected.target.resolve(strict=False)) if inspected.target else None
            if inspected.kind == "junction" and inspected.target and _normalized(inspected.target) == _normalized(source):
                status, code = "pass", "JUNCTION_TARGET_MATCH"
            elif inspected.kind == "missing":
                status, code = "fail", "LINK_MISSING"
            elif inspected.kind == "junction":
                status, code = "fail", "JUNCTION_TARGET_MISMATCH"
            elif inspected.kind == "directory":
                status, code = "fail", "LINK_NOT_REPARSE_POINT"
            elif inspected.kind == "file":
                status, code = "fail", "LINK_NOT_DIRECTORY"
            elif inspected.kind == "other_reparse":
                status, code = "fail", "LINK_NOT_JUNCTION"
            else:
                status, code = "fail", "JUNCTION_TARGET_UNREADABLE"
        items.append({"name": link["name"], "path": str(link["path"]), "expected_target": str(source), "actual_target": actual, "status": status, "code": code})
    summary = {"verified": sum(item["status"] == "pass" for item in items), "failed": sum(item["status"] == "fail" for item in items), "skipped": sum(item["status"] == "skip" for item in items)}
    return {"command": "deployment-verify", "ok": summary["failed"] == 0, "project": str(project), "tool": tool, "source_root": str(source_claude), "platform": platform, "items": items, "summary": summary}
