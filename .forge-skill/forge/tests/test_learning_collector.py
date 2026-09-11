"""Regression tests for direct-host learning collection boundaries."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from forge_cli.learning_collector import _registry_file_lock, collect_imported_result, connect_database
from forge_cli.runtime_paths import forge_runtime_directory


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
    shutil.copy2(SOURCE_FORGE / "forge_cli" / "data_paths.py", package / "data_paths.py")
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


def project_database(forge_root: Path, project: Path) -> Path:
    identity = json.loads((project / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8"))
    return forge_root.parent / "forge-data" / "projects" / identity["projectId"] / "learning" / "code-review" / "learning.sqlite"


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
    database = project_database(forge_root, project)
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
    assert not (forge_root.parent / "forge-data").exists()


def test_direct_collection_rejects_lone_surrogate_without_creating_database(tmp_path):
    forge_root, script = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    completed = run_direct(script, forge_root, project, b'{"conclusion":"\\udcac"}')

    assert completed.returncode != 0
    assert b"lone low surrogate" in completed.stderr
    assert not (forge_root.parent / "forge-data").exists()


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
    assert not (forge_root.parent / "forge-data").exists()


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

    identity = json.loads((project / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8"))
    data_root = forge_root.parent / "forge-data" / "projects" / identity["projectId"] / "learning"
    rows = []
    for skill in ("code-review", "debug", "explain"):
        with sqlite3.connect(data_root / skill / "learning.sqlite") as connection:
            rows.extend(connection.execute("SELECT skill, output_json FROM learning_records").fetchall())
    assert [row[0] for row in sorted(rows)] == ["code-review", "debug", "explain"]
    assert json.loads(rows[0][1]) == {"result": "code-review"}


def test_empty_result_is_skipped_before_database_creation(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)

    assert _collect(forge_root, project, "runtime.empty", "code-review", {}) is None

    assert not (forge_root.parent / "forge-data").exists()


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

    database = project_database(forge_root, project)
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
    assert "is_classic" in columns
    assert "classic_reason" in columns
    assert version == 6


def test_legacy_project_database_is_split_into_skill_data_roots(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path, ["code-review", "debug"])
    identity = {
        "schemaVersion": "1.0", "projectId": "project-legacy",
        "name": "project", "createdAt": "2026-01-01T00:00:00Z",
    }
    (project / ".forge-skill" / "learning" / "project.json").write_text(json.dumps(identity), encoding="utf-8")
    legacy = project / ".forge-skill" / "learning" / "learning.sqlite"
    connection = connect_database(legacy)
    for skill in ("code-review", "debug"):
        connection.execute(
            """INSERT INTO learning_records
               (id, project_id, project_name, project_path, skill, captured_at, output_json)
               VALUES (?, ?, 'project', ?, ?, '2026-01-01T00:00:00Z', '{}')""",
            (f"legacy-{skill}", identity["projectId"], str(project), skill),
        )
    connection.commit()
    connection.close()

    assert _collect(forge_root, project, "runtime-new", "code-review", {"result": "new"}) is not None

    data_root = forge_root.parent / "forge-data" / "projects" / identity["projectId"] / "learning"
    for skill in ("code-review", "debug"):
        with sqlite3.connect(data_root / skill / "learning.sqlite") as migrated:
            assert migrated.execute("SELECT DISTINCT skill FROM learning_records").fetchall() == [(skill,)]
    assert legacy.is_file()


def test_copied_project_gets_new_id_and_cloned_skill_databases(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    original = enabled_project(tmp_path / "original", ["code-review", "debug"])
    for skill in ("code-review", "debug"):
        _collect(forge_root, original, f"original-{skill}", skill, {"result": skill})
    original_identity = json.loads((original / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8"))
    original_database = (
        forge_root.parent / "forge-data" / "projects" / original_identity["projectId"]
        / "learning" / "code-review" / "learning.sqlite"
    )
    with sqlite3.connect(original_database) as connection:
        connection.execute(
            """INSERT INTO learning_summaries
               (id, project_id, skill, version, created_at, source_count, summary_json, applied)
               VALUES ('summary-original', ?, 'code-review', 1, '2026-01-01T00:00:00Z', 1, '{}', 1)""",
            (original_identity["projectId"],),
        )
        connection.commit()

    copied = tmp_path / "copied" / "project"
    shutil.copytree(original, copied)
    original_runtime = forge_runtime_directory(forge_root, original)
    copied_runtime = forge_runtime_directory(forge_root, copied)
    assert copied_runtime != original_runtime
    _collect(forge_root, copied, "copied-code-review", "code-review", {"result": "copy"})

    copied_identity = json.loads((copied / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8"))
    assert copied_identity["projectId"] != original_identity["projectId"]
    assert copied_identity["copiedFromProjectId"] == original_identity["projectId"]

    data_root = forge_root.parent / "forge-data" / "projects"
    original_code_review = data_root / original_identity["projectId"] / "learning" / "code-review" / "learning.sqlite"
    copied_learning = data_root / copied_identity["projectId"] / "learning"
    with sqlite3.connect(original_code_review) as connection:
        assert connection.execute("SELECT DISTINCT project_id FROM learning_records").fetchall() == [(original_identity["projectId"],)]
        assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 1
        assert connection.execute("SELECT applied FROM learning_summaries").fetchone()[0] == 1
    for skill in ("code-review", "debug"):
        with sqlite3.connect(copied_learning / skill / "learning.sqlite") as connection:
            assert connection.execute("SELECT DISTINCT project_id FROM learning_records").fetchall() == [(copied_identity["projectId"],)]
    with sqlite3.connect(copied_learning / "code-review" / "learning.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0] == 2
        assert connection.execute("SELECT applied FROM learning_summaries").fetchone()[0] == 0


def test_moved_project_updates_all_skill_record_paths(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    original = enabled_project(tmp_path / "original", ["code-review", "debug"])
    for skill in ("code-review", "debug"):
        _collect(forge_root, original, f"original-{skill}", skill, {"result": skill})
    identity = json.loads((original / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8"))

    moved = tmp_path / "moved" / "project"
    moved.parent.mkdir()
    original.rename(moved)
    assert identity["projectId"] in str(forge_runtime_directory(forge_root, moved))
    _collect(forge_root, moved, "moved-code-review", "code-review", {"result": "moved"})

    learning_root = forge_root.parent / "forge-data" / "projects" / identity["projectId"] / "learning"
    for skill in ("code-review", "debug"):
        with sqlite3.connect(learning_root / skill / "learning.sqlite") as connection:
            assert connection.execute("SELECT DISTINCT project_path FROM learning_records").fetchall() == [(str(moved),)]


def test_runtime_identity_fails_closed_when_registry_is_corrupt(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)
    (project / ".forge-skill" / "learning" / "project.json").write_text(
        json.dumps({"schemaVersion": "1.0", "projectId": "project-existing"}),
        encoding="utf-8",
    )
    registry = forge_root.parent / "forge-data" / "project-registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="cannot verify Forge project identity"):
        forge_runtime_directory(forge_root, project)


def test_runtime_identity_fails_closed_when_project_identity_is_corrupt(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)
    identity_path = project / ".forge-skill" / "learning" / "project.json"
    identity_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="cannot read Forge project identity"):
        forge_runtime_directory(forge_root, project)

    assert identity_path.read_text(encoding="utf-8") == "{invalid"


def test_runtime_identity_fails_closed_when_registered_path_is_missing(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path)
    identity_path = project / ".forge-skill" / "learning" / "project.json"
    identity_path.write_text(
        json.dumps({"schemaVersion": "1.0", "projectId": "project-existing"}),
        encoding="utf-8",
    )
    registry = forge_root.parent / "forge-data" / "project-registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps({"schemaVersion": "1.0", "projects": [{"projectId": "project-existing"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot verify Forge project identity"):
        forge_runtime_directory(forge_root, project)


def test_runtime_only_projects_are_registered_and_copies_receive_new_ids(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    original = enabled_project(tmp_path / "original")
    original_runtime = forge_runtime_directory(forge_root, original)
    original_identity = json.loads(
        (original / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8")
    )

    copied = tmp_path / "copied" / "project"
    shutil.copytree(original, copied)
    copied_runtime = forge_runtime_directory(forge_root, copied)
    copied_identity = json.loads(
        (copied / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8")
    )

    assert copied_identity["projectId"] != original_identity["projectId"]
    assert copied_runtime != original_runtime
    registry = json.loads(
        (forge_root.parent / "forge-data" / "project-registry.json").read_text(encoding="utf-8")
    )
    assert {item["projectId"] for item in registry["projects"]} == {
        original_identity["projectId"], copied_identity["projectId"],
    }


def test_runtime_identity_creation_waits_for_cross_process_registry_lock(tmp_path):
    forge_root, _ = isolated_collector(tmp_path)
    project = enabled_project(tmp_path / "project")
    registry = forge_root.parent / "forge-data" / "project-registry.json"
    ready = tmp_path / "child-ready"
    identity_path = project / ".forge-skill" / "learning" / "project.json"
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from forge_cli.runtime_paths import forge_runtime_directory\n"
        "Path(sys.argv[3]).write_text('ready', encoding='utf-8')\n"
        "forge_runtime_directory(Path(sys.argv[1]), Path(sys.argv[2]))\n"
    )

    registry.parent.mkdir(parents=True, exist_ok=True)
    with _registry_file_lock(registry):
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(forge_root), str(project), str(ready)],
            cwd=SOURCE_FORGE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 3
        while not ready.is_file() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.is_file(), "child process did not reach identity initialization"
        time.sleep(0.1)
        identity_created_while_locked = identity_path.exists()

    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, (stdout + stderr).decode("utf-8", errors="replace")
    assert identity_created_while_locked is False
    assert identity_path.is_file()
