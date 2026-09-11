"""Project-owned Forge Runtime path policy and legacy migration."""

from __future__ import annotations

import shutil
import json
import uuid
import os
import stat
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

from .data_paths import forge_data_root, project_runtime_data_root

PROJECT_RUNTIME_DIRECTORY = ".forge-runtime"
LEGACY_RUNTIME_DIRECTORY = ".forge" + "/runtime"
PROJECT_ID_PATTERN = re.compile(r"^project-[0-9a-fA-F-]{36}$")


def project_runtime_directory(project: Path) -> Path:
    return project.resolve() / PROJECT_RUNTIME_DIRECTORY


def _write_project_identity(identity_path: Path, value: dict) -> None:
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = identity_path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(identity_path)


def _project_id(forge_root: Path, project: Path) -> str:
    project = project.resolve()
    identity_path = project.resolve() / ".forge-skill" / "learning" / "project.json"
    registry_path = forge_data_root(forge_root) / "project-registry.json"
    from .learning_collector import (
        _REGISTRY_LOCK,
        _now,
        _registry_file_lock,
        _update_project_location,
    )

    with _REGISTRY_LOCK:
        try:
            with _registry_file_lock(registry_path):
                if identity_path.is_file():
                    try:
                        value = json.loads(identity_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError) as error:
                        raise ValueError(f"cannot read Forge project identity: {identity_path}") from error
                    project_id = value.get("projectId") if isinstance(value, dict) else None
                    if not isinstance(project_id, str) or not project_id.startswith("project-"):
                        raise ValueError(f"invalid Forge project identity: {identity_path}")
                else:
                    value = {
                        "schemaVersion": "1.0",
                        "projectId": f"project-{uuid.uuid4()}",
                        "name": project.name,
                        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    }
                    _write_project_identity(identity_path, value)
                    project_id = value["projectId"]

                try:
                    registry = (
                        json.loads(registry_path.read_text(encoding="utf-8"))
                        if registry_path.is_file()
                        else {"schemaVersion": "1.0", "projects": []}
                    )
                    if not isinstance(registry, dict):
                        raise ValueError("project registry must be an object")
                    entries = registry.get("projects", [])
                    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
                        raise ValueError("project registry projects must be an array of objects")
                    entry = next((item for item in entries if item.get("projectId", item.get("id")) == project_id), None)
                    if isinstance(entry, dict):
                        registered_path = entry.get("path")
                        if not isinstance(registered_path, str) or not registered_path.strip():
                            raise ValueError("registered project path must be a non-empty string")
                        previous_path = Path(registered_path)
                        current_path = project.resolve(strict=False)
                        if previous_path.resolve(strict=False) != current_path and previous_path.exists():
                            value = {
                                "schemaVersion": "1.0",
                                "projectId": f"project-{uuid.uuid4()}",
                                "name": project.name,
                                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                "copiedFromProjectId": project_id,
                            }
                            _write_project_identity(identity_path, value)
                            project_id = value["projectId"]
                            entry = None
                        elif previous_path.resolve(strict=False) != current_path:
                            _update_project_location(entry, project_id, project)
                            entry.update({
                                "name": project.name,
                                "path": str(project),
                                "status": "ACTIVE",
                                "lastSeenAt": _now(),
                            })
                    if entry is None:
                        entry = {
                            "projectId": project_id,
                            "name": project.name,
                            "path": str(project),
                            "databases": {},
                            "status": "ACTIVE",
                            "lastSeenAt": _now(),
                        }
                        if isinstance(value.get("copiedFromProjectId"), str):
                            entry["copiedFromProjectId"] = value["copiedFromProjectId"]
                        entries.append(entry)
                    registry["projects"] = entries
                    registry_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = registry_path.with_suffix(f".{os.getpid()}.json.tmp")
                    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    temporary.replace(registry_path)
                except (OSError, json.JSONDecodeError, ValueError) as error:
                    raise ValueError(
                        f"cannot verify Forge project identity from registry: {registry_path}"
                    ) from error
        except (OSError, json.JSONDecodeError, ValueError) as error:
            if isinstance(error, ValueError) and str(error).startswith(
                ("cannot read Forge project identity", "invalid Forge project identity")
            ):
                raise
            raise ValueError(
                f"cannot verify Forge project identity from registry: {registry_path}"
            ) from error
        return project_id


def forge_runtime_directory(forge_root: Path, project: Path) -> Path:
    return project_runtime_data_root(forge_root, _project_id(forge_root, project))


def _migrate_runtime_facade_directory(facade: Path, target: Path) -> None:
    entries = list(facade.iterdir())
    unsupported = [entry for entry in entries if not entry.is_file()]
    conflicts = [entry for entry in entries if (target / entry.name).exists()]
    if unsupported or conflicts:
        names = ", ".join(entry.name for entry in unsupported + conflicts)
        raise ValueError(f"cannot migrate existing .forge-runtime contents: {names}")
    target.mkdir(parents=True, exist_ok=True)
    moved: list[tuple[Path, Path]] = []
    try:
        for source in entries:
            destination = target / source.name
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
    except OSError as error:
        for source, destination in reversed(moved):
            try:
                shutil.move(str(destination), str(source))
            except OSError:
                pass
        raise ValueError("failed to migrate existing .forge-runtime contents") from error
    facade.rmdir()


def _directory_link_target(path: Path) -> Path | None:
    """Read symlink and Windows Junction targets on every supported Python."""
    try:
        value = os.readlink(path)
    except OSError:
        return None
    target = Path(value)
    return target if target.is_absolute() else path.parent / target


def _is_reparse_point(path: Path) -> bool:
    if os.name != "nt" or not hasattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT"):
        return False
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def ensure_runtime_facade(forge_root: Path, project: Path) -> Path:
    """Create the project-visible entry that points at global Runtime data."""
    target = forge_runtime_directory(forge_root, project)
    facade = project_runtime_directory(project)
    if os.path.lexists(facade):
        try:
            if facade.resolve() == target.resolve(strict=False):
                return facade
        except OSError:
            pass
        link_target = _directory_link_target(facade)
        if link_target is not None:
            if facade.is_symlink():
                facade.unlink()
            else:
                facade.rmdir()
        elif _is_reparse_point(facade):
            raise ValueError(".forge-runtime is an unsupported filesystem reparse point")
        elif facade.is_dir():
            _migrate_runtime_facade_directory(facade, target)
        else:
            raise ValueError(".forge-runtime exists and is not a directory facade")
    target.mkdir(parents=True, exist_ok=True)
    facade.parent.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(facade), str(target)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
            if completed.returncode:
                detail = (completed.stdout + completed.stderr).strip()
                raise ValueError(detail or "failed to create .forge-runtime Junction")
        else:
            facade.symlink_to(target, target_is_directory=True)
    except OSError as error:
        raise ValueError("failed to create .forge-runtime facade") from error
    return facade


def validate_project_runtime_directory(
    directory: Path, project: Path | None = None, expected_directory: Path | None = None
) -> Path:
    expected = (expected_directory or project_runtime_directory(project or Path.cwd())).resolve(strict=False)
    resolved = directory.resolve()
    if resolved != expected:
        raise ValueError(
            "runtime directory must belong to the current project's .forge-runtime directory; "
            "global stores must be partitioned by project id"
        )
    return resolved


def migrate_legacy_runtime_directory(project: Path, target: Path | None = None) -> list[dict[str, str]]:
    """Move legacy runtime files without overwriting newer project state."""
    legacy = project.resolve() / LEGACY_RUNTIME_DIRECTORY
    target = target or project_runtime_directory(project)
    if not legacy.is_dir():
        return []
    target.mkdir(parents=True, exist_ok=True)
    diagnostics: list[dict[str, str]] = []
    for source in sorted(legacy.iterdir(), key=lambda item: item.name.lower()):
        if not source.is_file():
            continue
        destination = target / source.name
        if destination.exists():
            diagnostics.append({"code": "LEGACY_RUNTIME_CONFLICT", "path": source.name})
            continue
        try:
            shutil.move(str(source), str(destination))
        except OSError as error:
            diagnostics.append({
                "code": "LEGACY_RUNTIME_MIGRATION_FAILED",
                "path": source.name,
                "message": str(error),
            })
    return diagnostics


def find_orphan_runtime_projects(forge_root: Path) -> list[dict[str, object]]:
    """Return central Runtime project directories absent from the registry."""
    data_root = forge_data_root(forge_root)
    projects_root = data_root / "projects"
    registry_path = data_root / "project-registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        raise ValueError(f"cannot read Forge project registry: {registry_path}")
    entries = registry.get("projects", []) if isinstance(registry, dict) else []
    registered = {item.get("projectId", item.get("id")) for item in entries if isinstance(item, dict)}
    if not projects_root.is_dir():
        return []
    result = []
    for directory in sorted(projects_root.iterdir(), key=lambda item: item.name.lower()):
        if not directory.is_dir() or directory.name in registered:
            continue
        if not PROJECT_ID_PATTERN.fullmatch(directory.name):
            continue
        files = [item for item in directory.rglob("*") if item.is_file()]
        result.append({"projectId": directory.name, "path": str(directory), "files": len(files), "bytes": sum(item.stat().st_size for item in files)})
    return result


def remove_orphan_runtime_project(forge_root: Path, project_id: str) -> dict[str, object]:
    """Physically remove one explicitly selected, unregistered Runtime project."""
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("invalid orphan project id")
    orphan = next((item for item in find_orphan_runtime_projects(forge_root) if item["projectId"] == project_id), None)
    if orphan is None:
        raise ValueError("project is registered or orphan Runtime data was not found")
    target = forge_data_root(forge_root) / "projects" / project_id
    shutil.rmtree(target)
    return orphan
