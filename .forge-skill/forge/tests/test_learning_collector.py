"""Regression tests for direct-host learning collection boundaries."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from forge_cli.learning_collector import collect_imported_result, connect_database


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FORGE = REPOSITORY_ROOT / "forge"
SOURCE_SCRIPT = REPOSITORY_ROOT / "skills" / "learning-collector" / "scripts" / "record_direct_result.py"


def isolated_collector(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    forge_root = bundle / "forge"
    package = forge_root / "forge_cli"
    package.mkdir(parents=True)
    shutil.copy2(SOURCE_FORGE / "forge_cli" / "__init__.py", package / "__init__.py")
    shutil.copy2(SOURCE_FORGE / "forge_cli" / "learning_collector.py", package / "learning_collector.py")
    script = bundle / "skills" / "learning-collector" / "scripts" / "record_direct_result.py"
    script.parent.mkdir(parents=True)
    shutil.copy2(SOURCE_SCRIPT, script)
    return forge_root, script


def enabled_project(tmp_path: Path, skills=None) -> Path:
    project = tmp_path / "project"
    learning = project / ".forge-skill" / "learning"
    learning.mkdir(parents=True)
    (learning / "config.json").write_text(
        json.dumps({"schemaVersion": "1.0", "enabledSkills": skills or ["code-review"]}),
        encoding="utf-8",
    )
    return project


def run_direct(script: Path, forge_root: Path, project: Path, payload: bytes) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-S", str(script), "--skill", "code-review", "--project", str(project), "--forge-root", str(forge_root)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=2,
        check=False,
    )


def test_direct_collection_needs_no_click_and_preserves_unicode(tmp_path):
    forge_root, script = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)
    payload = {"status": "succeeded", "conclusion": "中文审查 😀 𠀀"}

    completed = run_direct(
        script,
        forge_root,
        project,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    with sqlite3.connect(database) as connection:
        stored = connection.execute("SELECT output_json FROM learning_records").fetchone()[0]
    assert stored.isascii()
    assert json.loads(stored) == {"conclusion": "中文审查 😀 𠀀"}


def test_direct_collection_rejects_non_utf8_without_creating_database(tmp_path):
    forge_root, script = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    completed = run_direct(script, forge_root, project, b'{"conclusion":"\xff"}')

    assert completed.returncode != 0
    assert b"must be UTF-8 bytes" in completed.stderr
    assert not (project / ".forge-skill" / "learning" / "learning.sqlite").exists()


def test_direct_collection_rejects_lone_surrogate_without_creating_database(tmp_path):
    forge_root, script = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    completed = run_direct(script, forge_root, project, b'{"conclusion":"\\udcac"}')

    assert completed.returncode != 0
    assert b"lone low surrogate" in completed.stderr
    assert not (project / ".forge-skill" / "learning" / "learning.sqlite").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "succeeded"},
        {"status": "succeeded", "findings": []},
        {"status": "succeeded", "result": {"items": ["  ", {}, []]}},
        {"status": "succeeded", "diagnostics": [], "metadata": {}},
    ],
)
def test_direct_collection_skips_transport_only_and_recursively_empty_payloads(tmp_path, payload):
    forge_root, script = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    completed = run_direct(script, forge_root, project, json.dumps(payload).encode("utf-8"))

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert json.loads(completed.stdout) == {"collected": False, "database": None}
    assert not (project / ".forge-skill" / "learning" / "learning.sqlite").exists()


def _collect(forge_root, project, run_id, skill, output):
    envelope = {
        "runtime_id": run_id,
        "resolved_context": {"selection": {"skill": f"skill.{skill.replace('-', '_')}"}},
        "stage_progress": {"active_request": {"stage_id": "engine.delivery"}},
    }
    result = {"status": "succeeded", "output": output, "diagnostics": [], "metadata": {}}
    return collect_imported_result(forge_root, envelope, result, project=project)


def test_one_toolchain_stores_each_enabled_skill_once(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path, ["code-review", "debug", "explain"])

    for skill in ("code-review", "debug", "explain"):
        assert _collect(forge_root, project, "runtime.toolchain", skill, {"result": skill}) is not None
    assert _collect(forge_root, project, "runtime.toolchain", "code-review", {"result": "duplicate"}) is not None

    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT skill, output_json FROM learning_records ORDER BY skill"
        ).fetchall()
    assert [row[0] for row in rows] == ["code-review", "debug", "explain"]
    assert json.loads(rows[0][1]) == {"result": "code-review"}


def test_empty_result_is_skipped_before_database_creation(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    assert _collect(forge_root, project, "runtime.empty", "code-review", {}) is None

    assert not (project / ".forge-skill" / "learning" / "learning.sqlite").exists()


def test_diagnostics_only_record_does_not_store_empty_output_json(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)
    envelope = {
        "runtime_id": "runtime.failed",
        "resolved_context": {"selection": {"skill": "skill.code_review"}},
        "stage_progress": {"active_request": {"stage_id": "engine.delivery"}},
    }
    result = {
        "status": "failed",
        "output": {},
        "diagnostics": [{"type": "ValidationError", "message": "invalid review output"}],
        "metadata": {},
    }

    assert collect_imported_result(forge_root, envelope, result, project=project) is not None

    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    with sqlite3.connect(database) as connection:
        output_json, diagnostics_json = connection.execute(
            "SELECT output_json, diagnostics_json FROM learning_records"
        ).fetchone()
    assert output_json is None
    assert json.loads(diagnostics_json) == result["diagnostics"]


def test_existing_database_migration_preserves_records(tmp_path):
    database = tmp_path / "learning.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE learning_records (
            id TEXT PRIMARY KEY, project_id TEXT, project_name TEXT,
            project_path TEXT, skill TEXT, run_id TEXT, stage TEXT,
            run_status TEXT, captured_at TEXT, output_json TEXT,
            diagnostics_json TEXT, metadata_json TEXT, evaluation_json TEXT,
            review_status TEXT, reviewed INTEGER, edited_content TEXT,
            review_note TEXT, reviewed_at TEXT, deleted_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO learning_records (
            id, project_id, project_name, project_path, skill, run_id,
            captured_at, output_json, review_status, reviewed, review_note
        ) VALUES ('old', 'project-old', 'old', 'C:/old', 'code-review',
                  'runtime.old', '2026-08-27T00:00:00Z', '{}', 'ACTIVE', 0, '')
        """
    )
    connection.commit()
    connection.close()

    migrated = connect_database(database)
    try:
        columns = {row["name"] for row in migrated.execute("PRAGMA table_info(learning_records)")}
        count = migrated.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0]
        version = migrated.execute("PRAGMA user_version").fetchone()[0]
    finally:
        migrated.close()

    assert count == 1
    assert "collection_key" in columns
    assert version == 6
    assert "is_classic" in columns
    assert "classic_reason" in columns
