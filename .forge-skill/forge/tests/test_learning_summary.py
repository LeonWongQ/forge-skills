from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "skills" / "learning-collector" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import review_server
from forge_cli.learning_collector import connect_database
from summary_engine import build_code_review_summary, build_generic_summary, encoded_size


def finding(title: str, direction: str, severity: str = "High") -> dict:
    return {
        "title": title,
        "severity": severity,
        "suggested_direction": direction,
        "why_it_matters": "The current implementation can lose project registration data.",
        "confidence": "High",
    }


def test_code_review_summary_clusters_related_findings_and_stays_compact():
    records = [
        {"recordId": "r1", "capturedAt": "2026-09-01T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("项目注册表的读改写没有并发保护，可能丢失注册项目", "使用跨平台文件锁保护注册表读改写。")]}},
        {"recordId": "r2", "capturedAt": "2026-09-02T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("注册表锁仅限单个 Python 进程，跨进程仍可能丢失项目", "使用跨平台文件锁或 SQLite registry。")]}},
        {"recordId": "r3", "capturedAt": "2026-09-03T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("项目身份文件初始化不受注册锁保护", "将 project.json 初始化放入同一个跨进程锁。")]}},
        {"recordId": "r4", "capturedAt": "2026-09-04T00:00:00Z", "reviewNote": "", "content": {"findings": [
            finding("汇总响应体没有大小上限", "限制汇总响应体大小并按需读取详情。", "Medium")]}},
    ]

    summary = build_code_review_summary(records)

    assert summary["statistics"]["originalFindings"] == 4
    assert summary["statistics"]["candidateClusters"] == 3
    assert summary["rules"][0]["supportCount"] == 2
    assert summary["rules"][0]["sourceRecordIds"] == ["r1", "r2"]
    assert all(rule["status"] == "PENDING" for rule in summary["rules"])
    assert encoded_size(summary) < 20_000
    assert "findings" not in summary


def test_code_review_summary_caps_visible_source_ids_without_losing_support_count():
    records = [
        {"recordId": f"record-{index:03d}", "capturedAt": f"2026-09-01T00:00:{index:02d}Z",
         "reviewNote": "", "content": {"findings": [
             finding("并发写入没有事务保护", "检查并发写入的事务边界。")]}}
        for index in range(30)
    ]

    summary = build_code_review_summary(records)
    rule = summary["rules"][0]

    assert rule["supportCount"] == 30
    assert len(rule["sourceRecordIds"]) == 20
    assert rule["sourceIdsTruncated"] is True
    assert encoded_size(summary) < 20_000


def test_generic_summary_preserves_reviewed_content_as_pending_candidate():
    summary = build_generic_summary([
        {"recordId": "generic-1", "content": {"conclusion": "保持 API 错误码稳定。"}}
    ], skill="page-test")
    assert summary["quality"]["semanticInference"] is False
    assert summary["rules"][0]["status"] == "PENDING"
    assert "错误码" in summary["rules"][0]["instruction"]


def test_create_review_and_apply_v4_summary_filters_ineligible_records(tmp_path, monkeypatch):
    project = tmp_path / "project"
    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    database.parent.mkdir(parents=True)
    connection = connect_database(database)
    project_id = "project-test"
    base = (project_id, "project", str(project), "code-review", "run", "delivery", "succeeded")
    rows = [
        ("reviewed", *base, "2026-09-01T00:00:00Z", json.dumps({"findings": [finding("并发写入没有事务保护", "检查并发写入的事务边界。")]}), "ACTIVE", 1),
        ("unreviewed", *base, "2026-09-02T00:00:00Z", json.dumps({"findings": [finding("未审核问题", "不应进入汇总。")]}), "ACTIVE", 0),
        ("excluded", *base, "2026-09-03T00:00:00Z", json.dumps({"findings": [finding("已排除问题", "不应进入汇总。")]}), "EXCLUDED", 1),
    ]
    connection.executemany(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, run_id, stage, run_status,
            captured_at, output_json, review_status, reviewed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    connection.commit()
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project), "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})

    created = review_server.create_summary({"projectId": project_id, "skill": "code-review"})

    assert created["sourceCount"] == 1
    assert created["summary"]["format"] == "forge-skill-training-summary-v5"
    assert created["summary"]["status"] == "DRAFT"
    assert created["summary"]["statistics"]["eligibleRecords"] == 1
    rule = created["summary"]["rules"][0]
    with pytest.raises(ValueError, match="fully reviewed"):
        review_server.apply_summary({"projectId": project_id, "skill": "code-review", "version": 1})
    reviewed = review_server.review_summary({
        "projectId": project_id, "skill": "code-review", "version": created["version"],
        "rules": [{"id": rule["id"], "stage": "PRE_CHECK", "status": "CONFIRMED",
                   "instruction": "检查并发写入是否具备明确的事务边界。"}],
    })
    assert reviewed["status"] == "REVIEWED"

    applied = review_server.apply_summary({"projectId": project_id, "skill": "code-review", "version": 1})
    assert applied["applied"] is True
    saved = json.loads((project / ".forge-skill" / "learning" / "applied" / "code-review.json").read_text(encoding="utf-8"))
    assert saved["status"] == "REVIEWED"
    with sqlite3.connect(database) as check:
        assert check.execute("SELECT COUNT(*) FROM learning_summary_sources").fetchone()[0] == 1

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE learning_records SET captured_at = ?, is_classic = 1, classic_reason = ? WHERE id = ?",
        ("2020-01-01T00:00:00Z", "长期保留的回归案例", "reviewed"),
    )
    connection.commit()
    connection.close()
    second = review_server.create_summary({"projectId": project_id, "skill": "code-review"})
    assert second["version"] == 2
    assert second["sourceCount"] == 1
    assert second["summary"]["window"]["classicRecords"] == 1
    deleted = review_server.delete_summary({"projectId": project_id, "skill": "code-review", "version": 2})
    assert deleted["deleted"] is True
    with sqlite3.connect(database) as check:
        assert check.execute("SELECT COUNT(*) FROM learning_summaries WHERE version = 2").fetchone()[0] == 0
        assert check.execute(
            "SELECT COUNT(*) FROM learning_summary_sources s "
            "LEFT JOIN learning_summaries v ON v.id = s.summary_id WHERE v.id IS NULL"
        ).fetchone()[0] == 0


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        if self.offset >= len(self.payload):
            return b""
        if size is None or size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


def _draft_for_refinement(tmp_path, monkeypatch):
    project = tmp_path / "refine-project"
    database = project / ".forge-skill" / "learning" / "learning.sqlite"
    database.parent.mkdir(parents=True)
    connection = connect_database(database)
    project_id = "refine-project"
    base = (project_id, "project", str(project), "code-review", "run-1", "delivery", "succeeded")
    connection.execute(
        """INSERT INTO learning_records
           (id, project_id, project_name, project_path, skill, run_id, stage, run_status,
            captured_at, output_json, review_status, reviewed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1)""",
        ("record-1", *base, "2026-09-01T00:00:00Z",
         json.dumps({"findings": [finding("并发写入没有事务保护", "检查事务边界。")]})),
    )
    connection.commit()
    connection.close()
    registry_item = {"projectId": project_id, "name": "project", "path": str(project), "database": str(database)}
    monkeypatch.setattr(review_server, "projects", lambda: [registry_item])
    monkeypatch.setattr(review_server, "_enabled_skills", lambda _: {"code-review"})
    created = review_server.create_summary({"projectId": project_id, "skill": "code-review"})
    config_path = tmp_path / "llm-refiner.json"
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    monkeypatch.setattr(review_server, "_environment_value", lambda _name: "test-key")
    return project_id, database, created["version"]


def test_refine_uses_responses_api_and_persists_rule_sources(tmp_path, monkeypatch):
    project_id, database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    calls = []
    response_payload = {"output_text": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "type": "workflow",
        "title": "检查事务边界", "instruction": "检查并发写入是否具备事务边界。",
        "rationale": "重复证据", "status": "PENDING", "supportCount": 1,
        "sourceRecordIds": ["record-1"], "confidence": "High",
    }]}, ensure_ascii=False)}

    def fake_urlopen(request, timeout):
        calls.append((request, timeout, json.loads(request.data.decode("utf-8"))))
        return _FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(review_server.urllib.request, "urlopen", fake_urlopen)
    refined = review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})
    assert calls[0][2]["input"]
    assert "messages" not in calls[0][2]
    assert refined["summary"]["refinement"]["mode"] == "explicit_llm"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT rule_id, record_id FROM learning_summary_rule_sources").fetchall() == [("rule-1", "record-1")]


def test_refine_uses_chat_completions_and_rejects_empty_sources(tmp_path, monkeypatch):
    project_id, _database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/chat/completions",
        "model": "test-model", "wireApi": "chat_completions", "apiKeyEnv": "TEST_KEY",
    })
    payload = {"choices": [{"message": {"content": json.dumps({"rules": [{
        "id": "rule-1", "stage": "PRE_CHECK", "status": "PENDING",
        "instruction": "检查事务边界。", "sourceRecordIds": [],
    }]})}}]}
    monkeypatch.setattr(review_server.urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="source IDs"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


def test_refine_rejects_oversized_response_before_parsing(tmp_path, monkeypatch):
    project_id, _database, version = _draft_for_refinement(tmp_path, monkeypatch)
    review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    oversized = b"{" + b"x" * (review_server.MAX_LLM_RESPONSE_BYTES + 1)
    monkeypatch.setattr(review_server.urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeResponse(oversized))
    with pytest.raises(ValueError, match="256 KB"):
        review_server.refine_summary({"projectId": project_id, "skill": "code-review", "version": version})


def test_save_llm_config_writes_complete_json_atomically(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    monkeypatch.setattr(review_server, "_environment_value", lambda _name: "test-key")
    saved = review_server.save_llm_config({
        "enabled": True, "endpoint": "https://example.test/v1/responses",
        "model": "test-model", "wireApi": "responses", "apiKeyEnv": "TEST_KEY",
    })
    assert saved["configured"] is True
    assert json.loads(config_path.read_text(encoding="utf-8"))["wireApi"] == "responses"
    assert not config_path.with_suffix(".json.tmp").exists()


def test_llm_endpoints_reject_non_object_and_malformed_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"enabled": True, "apiKeyEnv": None}), encoding="utf-8")
    monkeypatch.setattr(review_server, "LLM_CONFIG_PATH", config_path)
    assert review_server.llm_config_status()["configured"] is False
    with pytest.raises(ValueError, match="JSON object"):
        review_server.save_llm_config([])
    with pytest.raises(ValueError, match="JSON object"):
        review_server.refine_summary([])
