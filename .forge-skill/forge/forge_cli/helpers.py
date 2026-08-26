# -*- coding: utf-8 -*-
"""Forge CLI — helper utilities: path resolution, JSON I/O, text normalization."""

import json
import os
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

import click


TOOL_CONFIG_DIRECTORIES = {
    "claude": ".claude",
    "cursor": ".cursor",
    "codex": ".codex",
}
REPOSITORY_SOURCE_DIRECTORY = ".forge-skill"


def _logical_path(value: str | Path) -> Path:
    """Make a path absolute without resolving a Windows junction or symlink."""
    return Path(value).absolute()


def _is_forge_root(path: Path) -> bool:
    return (path / "registry").is_dir() and (path / "CLAUDE.md").is_file()


def _discover_project_forge_root() -> Optional[Path]:
    """Find a logical Forge installation from the current project directory."""
    current = _logical_path(Path.cwd())
    preferred_tool = os.getenv("FORGE_TOOL", "").casefold()
    directories = list(TOOL_CONFIG_DIRECTORIES.values())
    if preferred_tool in TOOL_CONFIG_DIRECTORIES:
        preferred_directory = TOOL_CONFIG_DIRECTORIES[preferred_tool]
        directories.remove(preferred_directory)
        directories.insert(0, preferred_directory)

    for directory in (current, *current.parents):
        if _is_forge_root(directory):
            return directory
        source_candidate = directory / REPOSITORY_SOURCE_DIRECTORY / "forge"
        if _is_forge_root(source_candidate):
            return source_candidate
        for config_directory in directories:
            candidate = directory / config_directory / "forge"
            if _is_forge_root(candidate):
                return candidate
    return None


def _discover_global_codex_forge_root() -> Optional[Path]:
    """Find the logical global Codex Forge installation, when available.

    This is deliberately a final fallback. A project deployment always wins so
    a project can pin its own Forge version. ``absolute()`` preserves a
    Junction's visible ``.codex`` path instead of exposing its source target.
    """
    candidate = _logical_path(Path.home() / ".codex" / "forge")
    return candidate if _is_forge_root(candidate) else None


def env_verbose() -> bool:
    return os.getenv("FORGE_VERBOSE", "").lower() in ("1", "true", "yes", "on")


def debug(ctx, msg: str):
    if ctx.obj.get("verbose"):
        click.echo(f"[DEBUG] {msg}", err=True)


def resolve_root(root: Optional[str]) -> Path:
    if root:
        return _logical_path(root)

    env_root = os.getenv("FORGE_ROOT")
    if env_root:
        return _logical_path(env_root)

    project_root = _discover_project_forge_root()
    if project_root:
        return project_root

    global_codex_root = _discover_global_codex_forge_root()
    if global_codex_root:
        return global_codex_root

    raise click.UsageError(
        "Forge root was not found in the current project. "
        "Run from a project with .codex/forge, .forge-skill/forge, or .cursor/forge, "
        "install Forge globally at ~/.codex/forge, or provide --root / FORGE_ROOT explicitly."
    )


def workspace_root_from_forge_root(root: Path) -> Path:
    return root.parent


def resolved_workspace_root_from_forge_root(root: Path) -> Path:
    """Return the physical workspace boundary used for symlink-safe checks."""
    return root.resolve().parent


def workspace_prefix_from_forge_root(root: Path) -> Optional[str]:
    """Return the deployed tool directory for a Forge root when known.

    Forge source lives below `.forge-skill`, while client installations live
    below their tool-specific directories. An unrecognized root has no prefix
    and must use a relative path rather than claiming a particular layout.
    """
    directory = _logical_path(root).parent.name
    if directory == REPOSITORY_SOURCE_DIRECTORY:
        return directory
    if directory in TOOL_CONFIG_DIRECTORIES.values():
        return directory
    configured_tool = os.getenv("FORGE_TOOL", "").casefold()
    return TOOL_CONFIG_DIRECTORIES.get(configured_tool)


def portable_path_from_forge_root(root: Path, path: Path) -> str:
    """Render a physical module path for the logical Forge host.

    Installed roots preserve their host prefix. Standalone roots instead use
    a relative path, so callers never receive a misleading `.claude/...`.
    """
    physical_root = root.resolve()
    physical_path = path.resolve()
    prefix = workspace_prefix_from_forge_root(root)
    if prefix:
        relative = physical_path.relative_to(physical_root.parent).as_posix()
        return f"{prefix}/{relative}"
    relative = os.path.relpath(physical_path, physical_root).replace("\\", "/")
    return f"./{relative}" if not relative.startswith("../") else relative


# Compatibility alias for callers outside this package.
def claude_root_from_forge_root(root: Path) -> Path:
    return workspace_root_from_forge_root(root)


def _registered_path_error(code: str, value: Any, **details: Any) -> Dict[str, Any]:
    error = {"code": code, "path": value}
    error.update(details)
    return error


def _is_anchored_registered_path(value: str) -> bool:
    """Return whether a registry value uses an OS-anchored path syntax.

    Registry values are portable relative paths. Parse both Windows and POSIX
    forms so a foreign-platform absolute path cannot bypass validation.
    """
    return (
        PurePosixPath(value).is_absolute()
        or bool(PureWindowsPath(value).drive)
        or bool(PureWindowsPath(value).root)
    )


def resolve_registered_path(root: Path, value: Any) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """Resolve a registered path only when its final target stays in `.claude`.

    The registry supports Forge-relative values and `.claude/...` workspace
    values. Resolution is symlink-aware so an existing in-workspace symlink
    cannot make a workspace-external target appear valid.
    """
    if not isinstance(value, str) or not value.strip():
        return None, _registered_path_error("REGISTERED_PATH_INVALID", value)

    normalized = value.replace("\\", "/")
    if _is_anchored_registered_path(normalized):
        return None, _registered_path_error("REGISTERED_PATH_ABSOLUTE", value)

    workspace_root = resolved_workspace_root_from_forge_root(root)
    prefixes = tuple(f"{directory}/" for directory in TOOL_CONFIG_DIRECTORIES.values())
    matching_prefix = next((prefix for prefix in prefixes if normalized.startswith(prefix)), None)
    if matching_prefix:
        # Registry paths remain portable across tool-specific deployments.
        candidate = workspace_root / normalized[len(matching_prefix):]
    elif normalized.startswith("./"):
        candidate = root / normalized[2:]
    else:
        candidate = root / normalized

    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        return None, _registered_path_error(
            "REGISTERED_PATH_ESCAPE", value, resolved_path=str(resolved)
        )
    return resolved, None


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_name_to_id_suffix(name: str) -> str:
    return name.replace("-", "_")


def now_ms() -> float:
    return time.perf_counter() * 1000


def format_exception_path(prefix: str, path_items: List[Any]) -> str:
    if not path_items:
        return prefix or "$"
    parts = [prefix or "$"]
    for item in path_items:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(f".{item}")
    return "".join(parts)


def load_json_file_safe(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return load_json(path), None
    except Exception as e:
        return None, str(e)


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def is_string_2d_list(value: Any) -> bool:
    return isinstance(value, list) and all(is_string_list(x) for x in value)
