"""End-to-end acceptance coverage for the project Skill training lifecycle."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "skills" / "learning-collector" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import review_server
from forge_cli.learning_collector import collect_imported_result
from forge_cli.overlay_runtime import load_active_overlay


def _collect(forge_root: Path, project: Path, run_id: str, output: dict, overlay: dict | None = None) -> Path | None:
    envelope = {
        "runtime_id": run_id,
        "resolved_context": {"selection": {"skill": "skill.code_review"}},
        "stage_progress": {"active_request": {"stage_id": "engine.delivery"}},
        "runtime_state": {"project_overlay": overlay},
    }
    return collect_imported_result(
        forge_root,
        envelope,
        {"status": "succeeded", "output": output, "diagnostics": [], "metadata": {}},
        project=project,
    )


def test_learning_lifecycle_closes_from_collection_to_feedback_disable(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    forge_root = bundle / "forge"
    skill_root = bundle / "skills" / "learning-collector"
    code_review_skill = bundle / "skills" / "code-review" / "SKILL.md"
    corpus = forge_root / "evals" / "skill-behavior-cases.json"
    code_review_skill.parent.mkdir(parents=True)
    corpus.parent.mkdir(parents=True)
    code_review_skill.write_bytes((REPOSITORY_ROOT / "skills" / "code-review" / "SKILL.md").read_bytes())
    corpus.write_bytes((REPOSITORY_ROOT / "forge" / "evals" / "skill-behavior-cases.json").read_bytes())

    project = tmp_path / "consumer-project"
    learning_config = project / ".forge-skill" / "learning" / "config.json"
    learning_config.parent.mkdir(parents=True)
    learning_config.write_text(
        json.dumps({"schemaVersion": "1.0", "enabledSkills": ["code-review"]}),
        encoding="utf-8",
    )
    initial_output = {"findings": [{
        "title": "Missing transaction boundary",
        "severity": "High",
        "evidence": "The update commits two dependent writes independently.",
        "impact": "A partial failure leaves inconsistent state.",
        "direction": "Wrap both writes in one explicit transaction.",
        "confidence": "High",
    }]}
    database = _collect(forge_root, project, "run-initial", initial_output)
    assert database is not None

    registry_path = bundle / "forge-data" / "project-registry.json"
    identity = json.loads(
        (project / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8")
    )
    project_id = identity["projectId"]
    monkeypatch.setattr(review_server, "FORGE_ROOT", forge_root)
    monkeypatch.setattr(review_server, "SKILL_ROOT", skill_root)
    monkeypatch.setattr(review_server, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(review_server, "LEGACY_REGISTRY_PATH", bundle / "missing-registry.json")

    with closing(sqlite3.connect(database)) as connection, connection:
        initial_record_id = connection.execute("SELECT id FROM learning_records").fetchone()[0]
    reviewed = review_server.update_record({
        "projectId": project_id, "recordId": initial_record_id, "action": "ACTIVE",
        "editedContent": json.dumps(initial_output), "note": "confirmed regression evidence",
    })
    assert reviewed == {"updated": True, "disabledOverlay": None}

    summary = review_server.create_summary({"projectId": project_id, "skill": "code-review"})
    assert summary["sourceCount"] == 1
    summary_rules = summary["summary"]["rules"]
    assert summary_rules
    reviewed_summary = review_server.review_summary({
        "projectId": project_id,
        "skill": "code-review",
        "version": summary["version"],
        "rules": [{
            "id": rule["id"], "stage": rule["stage"], "status": "CONFIRMED",
            "instruction": rule["instruction"],
        } for rule in summary_rules],
    })
    assert reviewed_summary["status"] == "REVIEWED"

    overlay = review_server.create_overlay({
        "projectId": project_id, "skill": "code-review",
        "summaryVersions": [summary["version"]],
    })
    reviewed_overlay = review_server.review_overlay({
        "projectId": project_id, "skill": "code-review",
        "overlayId": overlay["id"], "content": overlay["content"],
    })
    assert reviewed_overlay["status"] == "REVIEWED"

    skill_digest = "sha256:" + hashlib.sha256(code_review_skill.read_bytes()).hexdigest()
    corpus_digest = "sha256:" + hashlib.sha256(corpus.read_bytes()).hexdigest()
    monkeypatch.setattr(review_server, "_configured_llm", lambda: ({
        "model": "test-judge", "wireApi": "responses", "timeoutSeconds": 30,
        "endpoint": "https://example.test/v1/responses",
    }, "test-key"))
    monkeypatch.setattr(review_server, "evaluate_overlay", lambda **_kwargs: ({
        "format": "forge-overlay-behavior-evaluation-v1",
        "passed": True,
        "caseCount": 3,
        "confidence": "MEDIUM",
        "gates": [],
        "candidateOverlayDigest": reviewed_overlay["contentDigest"],
        "skillDigest": skill_digest,
        "corpusDigest": corpus_digest,
    }, {
        "format": "forge-overlay-behavior-evaluation-v1", "passed": True, "cases": [],
    }))
    published = review_server.evaluate_and_publish_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": overlay["id"],
    })
    assert published["status"] == "PUBLISHED"
    assert review_server.activate_overlay({
        "projectId": project_id, "skill": "code-review", "overlayId": overlay["id"],
    })["status"] == "ACTIVE"

    applied_overlay = load_active_overlay(forge_root, project, "code-review")
    assert applied_overlay is not None
    assert applied_overlay["id"] == overlay["id"]
    assert applied_overlay["contentDigest"] == reviewed_overlay["contentDigest"]

    for index in range(11):
        assert _collect(
            forge_root, project, f"run-feedback-{index}",
            {"conclusion": f"review result {index}"}, applied_overlay,
        ) == database
    with closing(sqlite3.connect(database)) as connection, connection:
        feedback_ids = [row[0] for row in connection.execute(
            "SELECT id FROM learning_records WHERE metadata_json LIKE '%appliedOverlay%' "
            "ORDER BY captured_at, id"
        ).fetchall()]
    assert len(feedback_ids) == 11
    disabled_event = None
    for index, record_id in enumerate(feedback_ids):
        result = review_server.update_record({
            "projectId": project_id,
            "recordId": record_id,
            "action": "EXCLUDED" if index < 4 else "ACTIVE",
        })
        disabled_event = result["disabledOverlay"] or disabled_event

    assert disabled_event is not None
    assert disabled_event["overlayId"] == overlay["id"]
    assert disabled_event["reviewedCount"] == 11
    assert disabled_event["negativeCount"] == 4
    assert load_active_overlay(forge_root, project, "code-review") is None
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute(
            "SELECT status FROM skill_overlays WHERE id = ?", (overlay["id"],)
        ).fetchone()[0] == "DISABLED"
