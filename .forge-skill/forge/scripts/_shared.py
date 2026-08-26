"""
Shared utilities for forge toolchain scripts.

Paths are resolved relative to:
- FORGE_ROOT: .forge-skill/forge/
- WORKSPACE_ROOT: the .claude/ directory containing forge/, skills/, rules/, etc.
"""

from pathlib import Path
import json
import logging
import os

SCRIPTS_DIR = Path(__file__).resolve().parent
FORGE_ROOT = SCRIPTS_DIR.parent
WORKSPACE_ROOT = FORGE_ROOT.parent

OK = "OK"
FAIL = "FAIL"
WARN = "WARN"


def setup_logging() -> None:
    """Configure root logger. Reads FORGE_VERBOSE env var for DEBUG level."""
    level = logging.DEBUG if os.getenv("FORGE_VERBOSE") == "1" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s | %(name)s | %(message)s",
    )


def get_forge_version() -> str:
    """Read forge version from registry/modules.json."""
    modules = load_json(FORGE_ROOT / "registry" / "modules.json")
    if modules:
        return modules.get("version", "unknown")
    return "unknown"


def forge_path(relative: str) -> Path:
    """Resolve a path relative to the forge root (.forge-skill/forge/)."""
    return FORGE_ROOT / relative


def workspace_path(relative: str) -> Path:
    """Resolve a path relative to the workspace root."""
    return WORKSPACE_ROOT / relative


def load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None on failure."""
    log = logging.getLogger("forge")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log.warning("INVALID JSON: %s — %s", path, e)
        return None
    except OSError as e:
        # Covers FileNotFoundError, IsADirectoryError, PermissionError, etc.
        # Reachable when, e.g., a pack entry omits its `path` field and
        # FORGE_ROOT / "" resolves to a directory.
        log.warning("FAILED to read: %s — %s", path, e)
        return None


def collect_ids(registry: dict, key: str) -> dict[str, dict]:
    """
    Collect a flat id→entry map from a registry file.

    Handles both flat list registries (behaviors.json, packs.json, etc.)
    and layered registries (modules.json with its "layers" structure).
    """
    log = logging.getLogger("forge")
    result = {}
    entries = registry.get(key, [])
    if isinstance(entries, list):
        for entry in entries:
            eid = entry.get("id")
            if eid:
                result[eid] = entry
            else:
                log.warning("entry missing 'id' — %s", entry)
    elif isinstance(entries, dict):
        for _layer, items in entries.items():
            if isinstance(items, list):
                for entry in items:
                    eid = entry.get("id")
                    if eid:
                        result[eid] = entry
                    else:
                        log.warning("entry missing 'id' in layer '%s' — %s", _layer, entry)
    return result


def file_exists(path: Path) -> bool:
    """Check if the given path refers to an existing file."""
    return path.is_file()
