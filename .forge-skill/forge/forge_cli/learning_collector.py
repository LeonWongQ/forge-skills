"""Opt-in SQLite collector for configured Forge Skills."""
from __future__ import annotations

import hashlib
import errno
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_paths import forge_data_root, skill_data_root

COLLECTOR_SKILL = "learning-collector"
DATABASE_NAME = "learning.sqlite"
DATABASE_SCHEMA_VERSION = 9
CAPTURE_SOURCES = {"RUNTIME", "SKILL_CONTRACT", "HOST_HOOK"}
HOOK_STATUSES = {"NOT_EXPECTED", "NOT_CONFIGURED", "PENDING", "CAPTURED", "MISSED"}
_REGISTRY_LOCK = threading.Lock()


@contextmanager
def _registry_file_lock(path: Path, *, timeout: float | None = None):
    if timeout is not None and timeout < 0:
        raise ValueError("lock timeout must be non-negative")
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    mode = msvcrt.LK_LOCK if deadline is None else msvcrt.LK_NBLCK
                    msvcrt.locking(handle.fileno(), mode, 1)
                else:
                    import fcntl
                    mode = fcntl.LOCK_EX if deadline is None else fcntl.LOCK_EX | fcntl.LOCK_NB
                    fcntl.flock(handle.fileno(), mode)
                locked = True
                break
            except OSError as error:
                if deadline is None or error.errno not in {
                    errno.EACCES, errno.EAGAIN, errno.EDEADLK,
                }:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"timed out acquiring file lock: {lock_path}") from error
                time.sleep(min(0.01, remaining))
        yield
    finally:
        try:
            if locked and os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif locked:
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


def connect_database(path: Path, *, timeout: float = 2) -> sqlite3.Connection:
    needs_initialization = not path.exists()
    connection = sqlite3.connect(path, timeout=timeout)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout=2000")
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if needs_initialization and str(journal_mode).lower() != "truncate":
            connection.execute("PRAGMA journal_mode=TRUNCATE")
        current_schema = connection.execute("PRAGMA user_version").fetchone()[0]
        records_exist = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_records'"
        ).fetchone() is not None
        record_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(learning_records)")
        }
        records_need_migration = records_exist and not {
            "invocation_id", "capture_source", "hook_host", "hook_status",
            "fallback_captured", "hook_captured_at", "host_output_json",
        }.issubset(record_columns)
        summaries_exist = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_summaries'"
        ).fetchone() is not None
        summaries_need_migration = summaries_exist and not any(
            row[1] == "lifecycle_status"
            for row in connection.execute("PRAGMA table_info(learning_summaries)")
        )
        overlays_exist = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'skill_overlays'"
        ).fetchone() is not None
        overlays_need_migration = not overlays_exist
        overlay_columns = {row[1] for row in connection.execute("PRAGMA table_info(skill_overlays)")}
        overlay_columns_need_migration = overlays_exist and not {"evaluation_json", "published_at"}.issubset(overlay_columns)
        if (current_schema < DATABASE_SCHEMA_VERSION or records_need_migration
                or summaries_need_migration or overlays_need_migration
                or overlay_columns_need_migration):
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
                    invocation_id TEXT,
                    capture_source TEXT NOT NULL DEFAULT 'RUNTIME'
                        CHECK (capture_source IN ('RUNTIME', 'SKILL_CONTRACT', 'HOST_HOOK')),
                    hook_host TEXT,
                    hook_status TEXT NOT NULL DEFAULT 'NOT_EXPECTED'
                        CHECK (hook_status IN ('NOT_EXPECTED', 'NOT_CONFIGURED', 'PENDING', 'CAPTURED', 'MISSED')),
                    fallback_captured INTEGER NOT NULL DEFAULT 0 CHECK (fallback_captured IN (0, 1)),
                    hook_captured_at TEXT,
                    host_output_json TEXT,
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
                if "invocation_id" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN invocation_id TEXT")
                if "capture_source" not in columns:
                    connection.execute(
                        "ALTER TABLE learning_records ADD COLUMN capture_source TEXT NOT NULL DEFAULT 'RUNTIME'"
                    )
                if "hook_host" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN hook_host TEXT")
                if "hook_status" not in columns:
                    connection.execute(
                        "ALTER TABLE learning_records ADD COLUMN hook_status TEXT NOT NULL DEFAULT 'NOT_EXPECTED'"
                    )
                if "fallback_captured" not in columns:
                    connection.execute(
                        "ALTER TABLE learning_records ADD COLUMN fallback_captured INTEGER NOT NULL DEFAULT 0"
                    )
                if "hook_captured_at" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN hook_captured_at TEXT")
                if "host_output_json" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN host_output_json TEXT")
                if "is_classic" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN is_classic INTEGER NOT NULL DEFAULT 0")
                if "classic_reason" not in columns:
                    connection.execute("ALTER TABLE learning_records ADD COLUMN classic_reason TEXT NOT NULL DEFAULT ''")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_skill ON learning_records(skill)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_review ON learning_records(review_status, reviewed)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_captured ON learning_records(captured_at DESC)")
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_filter_capture "
                    "ON learning_records(skill, review_status, reviewed, captured_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_dashboard "
                    "ON learning_records(skill, review_status, captured_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_run ON learning_records(run_id)"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_collection_key "
                    "ON learning_records(collection_key) WHERE collection_key IS NOT NULL"
                )
                # Version 7 collection keys already guarantee these rows are
                # unique. Older rows stay unkeyed rather than risking an
                # incorrect historical merge during migration.
                connection.execute(
                    "UPDATE learning_records SET invocation_id = run_id "
                    "WHERE invocation_id IS NULL AND collection_key IS NOT NULL "
                    "AND run_id IS NOT NULL AND trim(run_id) <> ''"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_invocation "
                    "ON learning_records(project_id, skill, invocation_id) "
                    "WHERE invocation_id IS NOT NULL"
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
                        lifecycle_status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (lifecycle_status IN ('DRAFT', 'REVIEWED', 'ARCHIVED', 'DELETED')),
                        UNIQUE(project_id, skill, version)
                    )
                    """
                )
                summary_columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(learning_summaries)")
                }
                if "lifecycle_status" not in summary_columns:
                    connection.execute(
                        "ALTER TABLE learning_summaries ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'DRAFT'"
                    )
                    connection.execute(
                        "UPDATE learning_summaries SET lifecycle_status = CASE "
                        "WHEN json_extract(summary_json, '$.status') = 'REVIEWED' THEN 'REVIEWED' "
                        "ELSE 'DRAFT' END"
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
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS skill_overlays (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        skill TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (status IN ('DRAFT', 'REVIEWED', 'ACTIVE', 'DISABLED', 'DELETED')),
                        content TEXT NOT NULL,
                        manifest_json TEXT NOT NULL,
                        content_digest TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        reviewed_at TEXT,
                        enabled_at TEXT,
                        disabled_at TEXT,
                        evaluation_json TEXT,
                        published_at TEXT,
                        UNIQUE(project_id, skill, version)
                    )"""
                )
                overlay_columns = {row["name"] for row in connection.execute("PRAGMA table_info(skill_overlays)")}
                if "evaluation_json" not in overlay_columns:
                    connection.execute("ALTER TABLE skill_overlays ADD COLUMN evaluation_json TEXT")
                if "published_at" not in overlay_columns:
                    connection.execute("ALTER TABLE skill_overlays ADD COLUMN published_at TEXT")
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_overlay "
                    "ON skill_overlays(project_id, skill) WHERE status = 'ACTIVE'"
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS skill_overlay_sources (
                        overlay_id TEXT NOT NULL,
                        summary_id TEXT NOT NULL,
                        summary_digest TEXT NOT NULL,
                        PRIMARY KEY(overlay_id, summary_id)
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_overlay_source_summary "
                    "ON skill_overlay_sources(summary_id)"
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


def _capture_context(envelope: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the identity shared by contract and host-hook collection."""
    raw = result.get("collection")
    collection = raw if isinstance(raw, dict) else {}
    run_id = envelope.get("runtime_id")
    invocation_id = collection.get("invocationId", run_id)
    if invocation_id is not None:
        if not isinstance(invocation_id, str) or not invocation_id.strip() or len(invocation_id) > 128:
            raise ValueError("collection invocationId must be a non-empty string of at most 128 characters")
        invocation_id = invocation_id.strip()
    source = collection.get("source", "RUNTIME")
    if source not in CAPTURE_SOURCES:
        raise ValueError(f"unsupported collection source: {source}")
    hook_host = collection.get("hookHost")
    if hook_host is not None and (not isinstance(hook_host, str) or not hook_host.strip()):
        raise ValueError("collection hookHost must be a non-empty string when provided")
    hook_status = collection.get("hookStatus")
    if hook_status is None:
        hook_status = "CAPTURED" if source == "HOST_HOOK" else "NOT_EXPECTED"
    if hook_status not in HOOK_STATUSES:
        raise ValueError(f"unsupported collection hookStatus: {hook_status}")
    if source == "HOST_HOOK" and hook_status != "CAPTURED":
        raise ValueError("HOST_HOOK collection must use CAPTURED hookStatus")
    return {
        "invocation_id": invocation_id,
        "source": source,
        "hook_host": hook_host.strip() if isinstance(hook_host, str) else None,
        "hook_status": hook_status,
    }


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
            summary_digests = {}
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
                summary_digests[row["id"]] = "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            # A copied project inherits reviewed candidates, but activating a
            # training version always requires a new explicit human action.
            connection.execute(
                "UPDATE learning_summaries SET lifecycle_status = "
                "CASE WHEN lifecycle_status = 'REVIEWED' THEN 'REVIEWED' ELSE 'ARCHIVED' END "
                "WHERE project_id = ?",
                (identity["projectId"],),
            )
            connection.executemany(
                "UPDATE skill_overlay_sources SET summary_digest = ? WHERE summary_id = ?",
                ((digest, summary_id) for summary_id, digest in summary_digests.items()),
            )
            # Copies retain their candidate content, never an approval or an
            # evaluation made for the original project's scope.
            for row in connection.execute(
                "SELECT id, manifest_json FROM skill_overlays WHERE project_id = ?", (previous_id,)
            ).fetchall():
                try:
                    manifest = json.loads(row["manifest_json"])
                    if not isinstance(manifest, dict):
                        raise ValueError("overlay manifest must be an object")
                    manifest["projectId"] = identity["projectId"]
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    raise ValueError(f"cannot clone overlay {row['id']}: invalid manifest") from error
                connection.execute(
                    """UPDATE skill_overlays SET project_id = ?, manifest_json = ?, status = 'DRAFT',
                       reviewed_at = NULL, enabled_at = NULL, disabled_at = NULL,
                       evaluation_json = NULL, published_at = NULL WHERE id = ?""",
                    (identity["projectId"], json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), row["id"]),
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
    value: dict[str, Any] = {
        "projectId": pid,
        "name": identity.get("name") or project.name,
        "path": str(project),
        "database": str(database),
        "databases": {**inherited_databases, skill: str(database)},
        "status": "ACTIVE",
        "disabledAt": None,
        "unavailableSince": None,
        "healthReason": None,
        "lastSeenAt": _now(),
    }
    if identity.get("copiedFromProjectId"):
        value["copiedFromProjectId"] = identity["copiedFromProjectId"]
    if entry is None:
        projects.append(value)
    else:
        existing_databases = entry.get("databases") if isinstance(entry.get("databases"), dict) else {}
        value["databases"] = {**existing_databases, skill: str(database)}
        stable_fields = (
            "projectId", "name", "path", "database", "databases", "status",
            "copiedFromProjectId", "disabledAt", "unavailableSince", "healthReason",
        )
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
    capture = _capture_context(envelope, result)
    has_output = has_meaningful_content(output)
    has_diagnostics = has_meaningful_content(diagnostics)
    if capture["source"] == "HOST_HOOK" and not has_output:
        return None
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
    invocation_id = capture["invocation_id"]
    collection_key = f"{pid}:{skill}:{invocation_id}" if invocation_id else None
    metadata = result.get("metadata")
    overlay = envelope.get("runtime_state", {}).get("project_overlay")
    if isinstance(overlay, dict):
        # Keep provenance compact; the reviewed content is already versioned in
        # the Overlay table and must not be duplicated in every learning row.
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        metadata["appliedOverlay"] = {
            "id": overlay.get("id"),
            "projectId": overlay.get("projectId"),
            "skill": overlay.get("skill"),
            "version": overlay.get("version"),
            "contentDigest": overlay.get("contentDigest"),
        }
    connection = connect_database(database)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id, capture_source, reviewed FROM learning_records "
                "WHERE project_id = ? AND skill = ? AND invocation_id = ?",
                (pid, skill, invocation_id),
            ).fetchone() if invocation_id else None
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO learning_records (
                        id, project_id, project_name, project_path, skill, run_id, stage,
                        run_status, captured_at, output_json, diagnostics_json,
                        metadata_json, evaluation_json, collection_key, invocation_id,
                        capture_source, hook_host, hook_status, fallback_captured,
                        hook_captured_at, host_output_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id, pid, project.name, str(project), skill,
                        run_id, active.get("stage_id"), result.get("status"),
                        timestamp, _json(output) if has_output else None,
                        _json(diagnostics) if has_diagnostics else None,
                        _json(metadata), None, collection_key, invocation_id,
                        capture["source"], capture["hook_host"], capture["hook_status"],
                        1 if capture["source"] == "SKILL_CONTRACT" else 0,
                        timestamp if capture["source"] == "HOST_HOOK" else None,
                        _json(output) if capture["source"] == "HOST_HOOK" else None,
                    ),
                )
            elif (capture["source"] == "HOST_HOOK"
                    and existing["capture_source"] != "HOST_HOOK"
                    and existing["reviewed"] == 0):
                # Preserve the Skill's structured result as the canonical
                # training input. The host-rendered response is complementary
                # evidence and must not erase structure or Overlay provenance.
                connection.execute(
                    """
                    UPDATE learning_records
                    SET host_output_json = ?,
                        hook_host = ?,
                        hook_status = 'CAPTURED', hook_captured_at = ?,
                        fallback_captured = CASE
                            WHEN capture_source = 'SKILL_CONTRACT' THEN 1
                            ELSE fallback_captured
                        END
                    WHERE id = ?
                    """,
                    (
                        _json(output),
                        capture["hook_host"], timestamp, existing["id"],
                    ),
                )
            elif (capture["source"] == "SKILL_CONTRACT"
                    and existing["capture_source"] == "HOST_HOOK"
                    and existing["reviewed"] == 0):
                # Arrival order must not change the canonical training input.
                # Replace the provisional host rendering with the Skill's
                # structured result while retaining the Hook evidence fields.
                connection.execute(
                    """
                    UPDATE learning_records
                    SET run_id = ?, stage = ?, run_status = ?,
                        output_json = ?, diagnostics_json = ?, metadata_json = ?,
                        capture_source = 'SKILL_CONTRACT', fallback_captured = 1
                    WHERE id = ?
                    """,
                    (
                        run_id, active.get("stage_id"), result.get("status"),
                        _json(output) if has_output else None,
                        _json(diagnostics) if has_diagnostics else None,
                        _json(metadata), existing["id"],
                    ),
                )
    finally:
        connection.close()
    return database
