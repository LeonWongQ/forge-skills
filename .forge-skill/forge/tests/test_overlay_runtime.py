# -*- coding: utf-8 -*-
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from forge_cli.claude_code_adapter import build_claude_code_host_request
from forge_cli.context_bundle import build_context_bundle
from forge_cli.learning_collector import collect_imported_result, connect_database
from forge_cli.overlay_runtime import load_active_overlay
from forge_cli.runtime_composition import initialize_runtime, prepare_adapter_request
from forge_cli.resolved_context import build_context_from_route
from forge_cli.cli import _execute_route


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT.parent / "skills" / "learning-collector" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
import review_server


def _project(tmp_path: Path, project_id: str = "project-11111111-1111-1111-1111-111111111111") -> Path:
    project = tmp_path / "project"
    identity = project / ".forge-skill" / "learning" / "project.json"
    identity.parent.mkdir(parents=True)
    identity.write_text(json.dumps({"projectId": project_id}), encoding="utf-8")
    (identity.parent / "config.json").write_text(
        json.dumps({"enabledSkills": ["code-review"]}), encoding="utf-8"
    )
    return project


def _overlay_database(tmp_path: Path, project_id: str, skill: str = "code-review", *, status: str = "ACTIVE", content: str = "# Project correction\n") -> Path:
    database = tmp_path / "forge-data" / "projects" / project_id / "learning" / skill / "learning.sqlite"
    database.parent.mkdir(parents=True)
    connection = connect_database(database)
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = {"projectId": project_id, "skill": skill, "executionSource": "content", "contentDigest": digest}
    evaluation = {"passed": True, "behavior": {
        "passed": True, "candidateOverlayDigest": digest,
        "skillDigest": "sha256:" + hashlib.sha256(
            (ROOT.parent / "skills" / skill / "SKILL.md").read_bytes()
        ).hexdigest(),
        "corpusDigest": "sha256:" + hashlib.sha256(
            (ROOT / "evals" / "skill-behavior-cases.json").read_bytes()
        ).hexdigest(),
    }}
    with connection:
        connection.execute(
            "INSERT INTO skill_overlays (id, project_id, skill, version, status, content, manifest_json, "
            "content_digest, created_at, evaluation_json, published_at) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, '2026-09-14T00:00:00Z', ?, '2026-09-14T00:01:00Z')",
            ("overlay-test", project_id, skill, status, content, json.dumps(manifest), digest,
             json.dumps(evaluation)),
        )
    connection.close()
    return database


def _registry(tmp_path: Path, project: Path, project_id: str, database: Path) -> None:
    registry = tmp_path / "forge-data" / "project-registry.json"
    registry.write_text(json.dumps({"schemaVersion": "1.0", "projects": [{
        "projectId": project_id, "path": str(project), "databases": {"code-review": str(database)},
    }]}), encoding="utf-8")


def test_active_overlay_is_project_and_skill_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)

    loaded = load_active_overlay(ROOT, project, "skill.code_review")
    assert loaded and loaded["id"] == "overlay-test"
    assert load_active_overlay(ROOT, project, "debug") is None
    other = _project(tmp_path / "other", "project-22222222-2222-2222-2222-222222222222")
    assert load_active_overlay(ROOT, other, "code-review") is None


def test_disabled_skill_prevents_overlay_loading(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)
    (project / ".forge-skill" / "learning" / "config.json").write_text(
        json.dumps({"enabledSkills": []}), encoding="utf-8"
    )

    assert load_active_overlay(ROOT, project, "code-review") is None


def test_direct_overlay_resolver_returns_identity_and_content(tmp_path, monkeypatch):
    data_root = tmp_path / "forge-data"
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data_root))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id, content="# Direct correction\n")
    _registry(tmp_path, project, project_id, database)
    script = ROOT.parent / "skills" / "learning-collector" / "scripts" / "resolve_direct_overlay.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--skill", "code-review", "--project", str(project),
         "--forge-root", str(ROOT)],
        check=True, capture_output=True, text=True,
        env={**os.environ, "FORGE_DATA_ROOT": str(data_root)},
    )

    result = json.loads(completed.stdout)
    assert result["overlay"]["id"] == "overlay-test"
    assert result["overlay"]["content"] == "# Direct correction\n"


def test_tampered_overlay_is_ignored_and_disabled_overlay_is_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id, content="content")
    _registry(tmp_path, project, project_id, database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE skill_overlays SET content = 'tampered' WHERE id = 'overlay-test'")
    connection.commit()
    connection.close()
    assert load_active_overlay(ROOT, project, "code-review") is None


def test_unpublished_or_failed_overlay_is_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("UPDATE skill_overlays SET published_at = NULL WHERE id = 'overlay-test'")
    assert load_active_overlay(ROOT, project, "code-review") is None

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE skill_overlays SET published_at = '2026-09-14T00:01:00Z', "
            "evaluation_json = ? WHERE id = 'overlay-test'",
            (json.dumps({"passed": False, "behavior": {"passed": False}}),),
        )
    assert load_active_overlay(ROOT, project, "code-review") is None

    connection = sqlite3.connect(database)
    connection.execute("UPDATE skill_overlays SET content = 'content', status = 'DISABLED' WHERE id = 'overlay-test'")
    connection.commit()
    connection.close()
    assert load_active_overlay(ROOT, project, "code-review") is None


def test_overlay_evaluated_against_stale_skill_is_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)

    with closing(sqlite3.connect(database)) as connection, connection:
        evaluation = json.loads(connection.execute(
            "SELECT evaluation_json FROM skill_overlays WHERE id = 'overlay-test'"
        ).fetchone()[0])
        evaluation["behavior"]["skillDigest"] = "sha256:" + "0" * 64
        connection.execute(
            "UPDATE skill_overlays SET evaluation_json = ? WHERE id = 'overlay-test'",
            (json.dumps(evaluation),),
        )

    assert load_active_overlay(ROOT, project, "code-review") is None


def test_overlay_evaluated_against_stale_corpus_is_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)
    assert load_active_overlay(ROOT, project, "code-review") is not None

    with closing(sqlite3.connect(database)) as connection, connection:
        evaluation = json.loads(connection.execute(
            "SELECT evaluation_json FROM skill_overlays WHERE id = 'overlay-test'"
        ).fetchone()[0])
        evaluation["behavior"]["corpusDigest"] = "sha256:" + "0" * 64
        connection.execute("UPDATE skill_overlays SET evaluation_json = ? WHERE id = 'overlay-test'",
                           (json.dumps(evaluation),))
    assert load_active_overlay(ROOT, project, "code-review") is None
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.row_factory = sqlite3.Row
        active = connection.execute("SELECT * FROM skill_overlays WHERE id = 'overlay-test'").fetchone()
        assert review_server._usable_active_baseline(active, "code-review") is False


def test_overlay_evaluation_uses_global_skill_when_active_baseline_is_stale(tmp_path, monkeypatch):
    project_id = "project-stale-baseline"
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "overlay.sqlite"
    connection = connect_database(database)
    digest = "sha256:" + hashlib.sha256(b"stale").hexdigest()
    connection.execute(
        "INSERT INTO skill_overlays (id, project_id, skill, version, status, content, manifest_json, "
        "content_digest, created_at, evaluation_json, published_at) VALUES (?, ?, 'code-review', 1, 'ACTIVE', ?, '{}', ?, ?, ?, ?)" ,
        ("stale", project_id, "stale", digest, "2026-09-14T00:00:00Z",
         json.dumps({"passed": True, "behavior": {
             "passed": True, "candidateOverlayDigest": digest,
             "skillDigest": "sha256:" + "0" * 64,
         }}), "2026-09-14T00:01:00Z"),
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(review_server, "projects", lambda: [{
        "projectId": project_id, "name": "project", "path": str(project), "database": str(database),
    }])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM skill_overlays WHERE id = 'stale'").fetchone()
    connection.close()
    assert review_server._usable_active_baseline(row, "code-review") is False


def test_active_baseline_snapshot_returns_valid_overlay_and_ignores_stale_one(tmp_path):
    project_id = "project-baseline-snapshot"
    database = _overlay_database(tmp_path, project_id)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        baseline = review_server._active_baseline_snapshot(
            connection, project_id, "code-review"
        )
        assert baseline and baseline["id"] == "overlay-test"
        evaluation = json.loads(connection.execute(
            "SELECT evaluation_json FROM skill_overlays WHERE id = 'overlay-test'"
        ).fetchone()[0])
        evaluation["behavior"]["skillDigest"] = "sha256:" + "0" * 64
        connection.execute(
            "UPDATE skill_overlays SET evaluation_json = ? WHERE id = 'overlay-test'",
            (json.dumps(evaluation),),
        )
        connection.commit()
        assert review_server._active_baseline_snapshot(
            connection, project_id, "code-review"
        ) is None
    finally:
        connection.close()


def test_runtime_and_claude_request_carry_active_overlay(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id, content="# Always cite the changed file.\n")
    _registry(tmp_path, project, project_id, database)
    manifest = build_context_from_route(ROOT, _execute_route(ROOT, "帮我 review 一个 spring service 改动"))
    runtime = initialize_runtime(ROOT, manifest, task_statement="帮我 review 一个 spring service 改动", project=project)
    assert runtime["runtime_state"]["project_overlay"]["version"] == 1
    assert any(event["event_type"] == "project_overlay_applied" for event in runtime["ledger"]["events"])
    runtime = prepare_adapter_request(ROOT, runtime)
    bundle = build_context_bundle(ROOT, runtime)
    request = build_claude_code_host_request(ROOT, runtime, bundle)
    runtime_segment = next(item for item in request["prompt"]["segments"] if item["kind"] == "runtime_state")
    assert "Always cite the changed file" in runtime_segment["content"]


def test_collection_keeps_overlay_provenance_without_copying_content(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    project = _project(tmp_path)
    (project / ".forge-skill" / "learning" / "config.json").write_text(
        json.dumps({"enabledSkills": ["code-review"]}), encoding="utf-8"
    )
    project_id = "project-11111111-1111-1111-1111-111111111111"
    database = _overlay_database(tmp_path, project_id)
    _registry(tmp_path, project, project_id, database)
    envelope = {
        "runtime_id": "runtime.overlay-provenance",
        "resolved_context": {"selection": {"skill": "skill.code_review"}},
        "stage_progress": {"active_request": {"stage_id": "engine.delivery"}},
        "runtime_state": {"project_overlay": {
            "id": "overlay-test", "projectId": project_id, "skill": "code-review", "version": 1,
            "content": "secretly detailed content", "contentDigest": "sha256:" + "0" * 64,
        }},
    }
    collect_imported_result(ROOT, envelope, {"status": "succeeded", "output": {"ok": True}, "metadata": {}}, project=project)
    with closing(sqlite3.connect(database)) as connection, connection:
        metadata = json.loads(connection.execute("SELECT metadata_json FROM learning_records").fetchone()[0])
    assert metadata["appliedOverlay"]["id"] == "overlay-test"
    assert "content" not in metadata["appliedOverlay"]
