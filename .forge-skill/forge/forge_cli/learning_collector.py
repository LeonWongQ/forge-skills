"""Opt-in SQLite collector for configured Forge Skills."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_paths import forge_data_root, skill_data_root

COLLECTOR_SKILL = "learning-collector"
DATABASE_NAME = "learning.sqlite"
DATABASE_SCHEMA_VERSION = 6
_REGISTRY_LOCK = threading.Lock()


@contextmanager
def _registry_file_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _skill_root(forge_root: Path) -> Path:
    base = forge_root.parent if forge_root.name == "forge" else forge_root
    return base / "skills" / COLLECTOR_SKILL


def _data_root(forge_root: Path) -> Path:
    return forge_data_root(forge_root)


def _project_database(forge_root: Path, project_id: str, skill: str) -> Path:
    return skill_data_root(forge_root, project_id, skill) / DATABASE_NAME


def _project_identity(project: Path) -> dict[str, str] | None:
    learning_dir = project / ".forge-skill" / "learning"
    identity_path = learning_dir / "project.json"
    if identity_path.is_file():
        try:
            value = json.loads(identity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        project_id = value.get("projectId") if isinstance(value, dict) else None
        return value if isinstance(project_id, str) and project_id.startswith("project-") else None
    learning_dir.mkdir(parents=True, exist_ok=True)
    value = {
        "schemaVersion": "1.0",
        "projectId": f"project-{uuid.uuid4()}",
        "name": project.name,
        "createdAt": _now(),
    }
    _write_project_identity(project, value)
    return value


def _write_project_identity(project: Path, identity: dict[str, str]) -> None:
    identity_path = project / ".forge-skill" / "learning" / "project.json"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = identity_path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.json.tmp")
    temporary.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(identity_path)


def _fork_project_identity(project: Path, identity: dict[str, str]) -> dict[str, str]:
    forked = {
        "schemaVersion": "1.0",
        "projectId": f"project-{uuid.uuid4()}",
        "name": project.name,
        "createdAt": _now(),
        "copiedFromProjectId": identity["projectId"],
    }
    _write_project_identity(project, forked)
    return forked


def _load_enabled_skills(forge_root: Path, project: Path) -> set[str] | None:
    project_config = project / ".forge-skill" / "learning" / "config.json"
    path = project_config if project_config.is_file() else _skill_root(forge_root) / "config.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    enabled = {item for item in value.get("enabledSkills", []) if isinstance(item, str)}
    enabled.discard(COLLECTOR_SKILL)
    return enabled


def connect_database(path: Path) -> sqlite3.Connection:
    needs_initialization = not path.exists()
    connection = sqlite3.connect(path, timeout=2)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout=2000")
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if needs_initialization and str(journal_mode).lower() != "truncate":
            connection.execute("PRAGMA journal_mode=TRUNCATE")
        if connection.execute("PRAGMA user_version").fetchone()[0] < DATABASE_SCHEMA_VERSION:
            with connection:
                connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_records (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    run_id TEXT,
                    stage TEXT,
                    run_status TEXT,
                    captured_at TEXT NOT NULL,
                    output_json TEXT,
                    diagnostics_json TEXT,
                    metadata_json TEXT,
                    evaluation_json TEXT,
                    collection_key TEXT,
                    review_status TEXT NOT NULL DEFAULT 'ACTIVE'
                        CHECK (review_status IN ('ACTIVE', 'EXCLUDED', 'DELETED')),
                    reviewed INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
                    edited_content TEXT,
                    review_note TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT,
                    deleted_at TEXT,
                    is_classic INTEGER NOT NULL DEFAULT 0 CHECK (is_classic IN (0, 1)),
                    classic_reason TEXT NOT NULL DEFAULT ''
                )
                """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(learning_records)")
                }
                if "collection_key" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN collection_key TEXT")
                if "is_classic" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN is_classic INTEGER NOT NULL DEFAULT 0")
                if "classic_reason" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN classic_reason TEXT NOT NULL DEFAULT ''")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_skill ON learning_records(skill)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_review ON learning_records(review_status, reviewed)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_captured ON learning_records(captured_at DESC)")
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_collection_key "
                    "ON learning_records(collection_key) WHERE collection_key IS NOT NULL"
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learning_summaries (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        skill TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        source_count INTEGER NOT NULL,
                        summary_json TEXT NOT NULL,
                        applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0, 1)),
                        UNIQUE(project_id, skill, version)
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_summary_skill "
                    "ON learning_summaries(project_id, skill, version DESC)"
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS learning_summary_sources (
                        summary_id TEXT NOT NULL,
                        record_id TEXT NOT NULL,
                        PRIMARY KEY(summary_id, record_id)
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_summary_source_record "
                    "ON learning_summary_sources(record_id)"
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS learning_summary_rule_sources (
                        summary_id TEXT NOT NULL,
                        rule_id TEXT NOT NULL,
                        record_id TEXT NOT NULL,
                        PRIMARY KEY(summary_id, rule_id, record_id)
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_summary_rule_source_record "
                    "ON learning_summary_rule_sources(record_id)"
                )
                connection.execute(f"PRAGMA user_version={DATABASE_SCHEMA_VERSION}")
    except Exception:
        connection.close()
        raise
    return connection


def _migrate_legacy_learning_database(forge_root: Path, project: Path, project_id: str) -> None:
    legacy = project / ".forge-skill" / "learning" / DATABASE_NAME
    if not legacy.is_file():
        return
    source = sqlite3.connect(legacy, timeout=2)
    try:
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "learning_records" not in tables:
            return
        skills = [row[0] for row in source.execute(
            "SELECT DISTINCT skill FROM learning_records WHERE skill IS NOT NULL AND trim(skill) <> ''"
        )]
        for skill in skills:
            target = _project_database(forge_root, project_id, skill)
            if target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(f".{os.getpid()}.sqlite.tmp")
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
                with destination:
                    destination.execute("DELETE FROM learning_records WHERE skill <> ?", (skill,))
                    if "learning_summaries" in tables:
                        obsolete = [row[0] for row in destination.execute(
                            "SELECT id FROM learning_summaries WHERE skill <> ?", (skill,)
                        )]
                        for summary_id in obsolete:
                            if "learning_summary_sources" in tables:
                                destination.execute("DELETE FROM learning_summary_sources WHERE summary_id = ?", (summary_id,))
                            if "learning_summary_rule_sources" in tables:
                                destination.execute("DELETE FROM learning_summary_rule_sources WHERE summary_id = ?", (summary_id,))
                        destination.execute("DELETE FROM learning_summaries WHERE skill <> ?", (skill,))
            finally:
                destination.close()
            temporary.replace(target)
    finally:
        source.close()


def _json(value: Any) -> str | None:
    if value is None:
        return None
    validate_no_lone_surrogates(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def has_meaningful_content(value: Any) -> bool:
    """Return whether a JSON-compatible value contains reviewable content."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_meaningful_content(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_meaningful_content(item) for item in value)
    return True


def validate_no_lone_surrogates(value: Any, path: str = "$") -> None:
    """Reject invalid Unicode while allowing well-formed escaped pairs."""
    if isinstance(value, str):
        index = 0
        while index < len(value):
            codepoint = ord(value[index])
            if 0xD800 <= codepoint <= 0xDBFF:
                if index + 1 >= len(value) or not 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                    raise ValueError(f"input contains a lone high surrogate at {path}[{index}]")
                index += 2
                continue
            if 0xDC00 <= codepoint <= 0xDFFF:
                raise ValueError(f"input contains a lone low surrogate at {path}[{index}]")
            index += 1
        return
    if isinstance(value, dict):
        for key, item in value.items():
            validate_no_lone_surrogates(key, f"{path}.<key>")
            validate_no_lone_surrogates(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_no_lone_surrogates(item, f"{path}[{index}]")


def _adopt_copied_database(database: Path, previous_id: str, identity: dict[str, str], project: Path) -> None:
    connection = connect_database(database)
    try:
        with connection:
            connection.execute(
                """
                UPDATE learning_records
                SET project_id = ?, project_name = ?, project_path = ?,
                    collection_key = CASE
                        WHEN collection_key LIKE ? THEN ? || substr(collection_key, length(?) + 1)
                        ELSE collection_key
                    END
                WHERE project_id = ?
                """,
                (
                    identity["projectId"], identity.get("name") or project.name, str(project),
                    f"{previous_id}:%", identity["projectId"], previous_id, previous_id,
                ),
            )
            rows = connection.execute(
                "SELECT id, summary_json FROM learning_summaries WHERE project_id = ?", (previous_id,)
            ).fetchall()
            for row in rows:
                try:
                    summary = json.loads(row["summary_json"])
                    summary["projectId"] = identity["projectId"]
                    summary["sourceRecords"] = [
                        {**item, "projectId": identity["projectId"]}
                        for item in summary.get("sourceRecords", [])
                    ]
                    encoded = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
                except (TypeError, json.JSONDecodeError) as error:
                    raise ValueError(f"cannot migrate summary {row['id']}: invalid summary_json") from error
                connection.execute(
                    "UPDATE learning_summaries SET project_id = ?, summary_json = ? WHERE id = ?",
                    (identity["projectId"], encoded, row["id"]),
                )
            # A copied project inherits reviewed candidates, but activating a
            # training version always requires a new explicit human action.
            connection.execute(
                "UPDATE learning_summaries SET applied = 0 WHERE project_id = ?",
                (identity["projectId"],),
            )
    finally:
        connection.close()


def _clone_project_learning_data(
    forge_root: Path,
    entry: dict[str, Any],
    previous_id: str,
    identity: dict[str, str],
    project: Path,
) -> dict[str, str]:
    """Clone inherited Skill learning data without modifying the source project."""
    databases = entry.get("databases")
    sources = databases if isinstance(databases, dict) else {}
    if not sources and isinstance(entry.get("database"), str):
        sources = {"code-review": entry["database"]}
    cloned: dict[str, str] = {}
    for skill, source_value in sources.items():
        if not isinstance(skill, str) or not isinstance(source_value, str):
            continue
        source = Path(source_value)
        if not source.is_file():
            continue
        target = _project_database(forge_root, identity["projectId"], skill)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_suffix(f".{os.getpid()}.sqlite.tmp")
            source_connection = sqlite3.connect(source, timeout=2)
            destination = sqlite3.connect(temporary)
            try:
                source_connection.backup(destination)
            finally:
                destination.close()
                source_connection.close()
            temporary.replace(target)
        _adopt_copied_database(target, previous_id, identity, project)
        cloned[skill] = str(target)
    return cloned


def _update_project_location(entry: dict[str, Any], project_id: str, project: Path) -> None:
    databases = entry.get("databases")
    values = databases.values() if isinstance(databases, dict) else [entry.get("database")]
    seen: set[Path] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        database = Path(value)
        if database in seen or not database.is_file():
            continue
        seen.add(database)
        connection = connect_database(database)
        try:
            with connection:
                connection.execute(
                    "UPDATE learning_records SET project_name = ?, project_path = ? WHERE project_id = ?",
                    (project.name, str(project), project_id),
                )
        finally:
            connection.close()


def _register_project(forge_root: Path, project: Path, database: Path, identity: dict[str, str], skill: str) -> dict[str, str]:
    with _REGISTRY_LOCK:
        registry_path = _data_root(forge_root) / "project-registry.json"
        with _registry_file_lock(registry_path):
            return _register_project_locked(forge_root, project, database, identity, skill)


def _register_project_locked(forge_root: Path, project: Path, database: Path, identity: dict[str, str], skill: str) -> dict[str, str]:
    registry_path = _data_root(forge_root) / "project-registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"schemaVersion": "1.0", "projects": []}
    except (OSError, json.JSONDecodeError) as error:
        if registry_path.is_file():
            corrupt = registry_path.with_suffix(".corrupt.json")
            try:
                shutil.copy2(registry_path, corrupt)
            except OSError:
                pass
            raise ValueError(f"project registry is unreadable; preserved at {corrupt}") from error
        registry = {"schemaVersion": "1.0", "projects": []}
    projects = registry.setdefault("projects", [])
    pid = identity["projectId"]
    entry = next((item for item in projects if item.get("projectId", item.get("id")) == pid), None)
    inherited_databases: dict[str, str] = {}
    if entry is not None:
        previous_path = Path(str(entry.get("path", "")))
        if previous_path.resolve(strict=False) != project.resolve(strict=False) and previous_path.exists():
            previous_id = pid
            identity = _fork_project_identity(project, identity)
            pid = identity["projectId"]
            inherited_databases = _clone_project_learning_data(
                forge_root, entry, previous_id, identity, project
            )
            database = _project_database(forge_root, pid, skill)
            entry = None
        elif previous_path.resolve(strict=False) != project.resolve(strict=False):
            _update_project_location(entry, pid, project)
    if (isinstance(identity.get("copiedFromProjectId"), str)
            and not inherited_databases
            and (entry is None or not entry.get("databases"))):
        source_entry = next(
            (
                item for item in projects
                if item.get("projectId", item.get("id")) == identity["copiedFromProjectId"]
            ),
            None,
        )
        if isinstance(source_entry, dict):
            inherited_databases = _clone_project_learning_data(
                forge_root, source_entry, identity["copiedFromProjectId"], identity, project
            )
            database = _project_database(forge_root, pid, skill)
    value: dict[str, str] = {
        "projectId": pid,
        "name": identity.get("name") or project.name,
        "path": str(project),
        "database": str(database),
        "databases": {**inherited_databases, skill: str(database)},
        "status": "ACTIVE",
        "lastSeenAt": _now(),
    }
    if identity.get("copiedFromProjectId"):
        value["copiedFromProjectId"] = identity["copiedFromProjectId"]
    if entry is None:
        projects.append(value)
    else:
        existing_databases = entry.get("databases") if isinstance(entry.get("databases"), dict) else {}
        value["databases"] = {**existing_databases, skill: str(database)}
        stable_fields = ("projectId", "name", "path", "database", "databases", "status", "copiedFromProjectId")
        if all(entry.get(field) == value.get(field) for field in stable_fields):
            return identity
        entry.pop("id", None)
        entry.pop("conflictingPath", None)
        entry.update(value)
    temporary = registry_path.with_suffix(f".{os.getpid()}.json.tmp")
    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(registry_path)
    return identity


def collect_imported_result(
    forge_root: Path,
    envelope: dict[str, Any],
    result: dict[str, Any],
    *,
    project: Path | None = None,
) -> Path | None:
    """Persist one result when its resolved Skill is enabled for this project."""
    project = (project or Path.cwd()).resolve()
    selection = envelope.get("resolved_context", {}).get("selection", {})
    skill = str(selection.get("skill") or "").removeprefix("skill.").replace("_", "-")
    output = result.get("output", result.get("document", result.get("content")))
    diagnostics = result.get("diagnostics")
    has_output = has_meaningful_content(output)
    has_diagnostics = has_meaningful_content(diagnostics)
    if not has_output and not has_diagnostics:
        return None
    enabled = _load_enabled_skills(forge_root, project)
    if enabled is None:
        return None
    if not skill or skill == COLLECTOR_SKILL or skill not in enabled:
        return None

    registry_path = _data_root(forge_root) / "project-registry.json"
    with _REGISTRY_LOCK:
        with _registry_file_lock(registry_path):
            identity = _project_identity(project)
            if identity is None:
                return None
            _migrate_legacy_learning_database(forge_root, project, identity["projectId"])
            database = _project_database(forge_root, identity["projectId"], skill)
            database.parent.mkdir(parents=True, exist_ok=True)
            identity = _register_project_locked(forge_root, project, database, identity, skill)
    database = _project_database(forge_root, identity["projectId"], skill)
    database.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _now()
    record_id = f"capture-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    active = envelope.get("stage_progress", {}).get("active_request", {}) or {}
    pid = identity["projectId"]
    run_id = envelope.get("runtime_id")
    collection_key = f"{pid}:{skill}:{run_id}" if isinstance(run_id, str) and run_id else None
    connection = connect_database(database)
    try:
        with connection:
            connection.execute(
            """
            INSERT INTO learning_records (
                id, project_id, project_name, project_path, skill, run_id, stage,
                run_status, captured_at, output_json, diagnostics_json,
                metadata_json, evaluation_json, collection_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_key) WHERE collection_key IS NOT NULL DO NOTHING
            """,
                (
                    record_id, pid, project.name, str(project), skill,
                    run_id, active.get("stage_id"), result.get("status"),
                    timestamp, _json(output) if has_output else None,
                    _json(diagnostics) if has_diagnostics else None,
                    _json(result.get("metadata")), None, collection_key,
                ),
            )
    finally:
        connection.close()
    return database
