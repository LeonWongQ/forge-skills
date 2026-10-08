"""Shared Skill criteria and bounded Summary evidence loading."""
from __future__ import annotations

import json

MAX_EVIDENCE_BYTES = 48_000
MAX_RECORD_BYTES = 16_000

SKILL_CRITERIA = {
    "code-review": "Keep reusable review checks or evidence/severity calibration; discard historical findings and file-specific fixes.",
    "debug": "Keep reusable diagnosis and verification steps; discard the incident's root cause as a general fact.",
    "implement": "Keep reusable implementation safeguards; discard project-specific decisions and changed files.",
    "page-test": "Keep reusable locator, wait, and assertion practices; discard a test run's results.",
    "test-implementation": "Keep reusable test coverage practices; discard a specific test case's expected value.",
    "refactor": "Keep reusable behavior-preservation and validation practices; discard the current target structure.",
    "explain": "Keep reusable teaching and misconception-handling practices; discard facts about the concept explained.",
    "plan": "Keep reusable sequencing, dependency, risk, and verification practices; discard the task-specific plan itself.",
    "explore": "Keep reusable discovery and decision practices; discard observations about the current project.",
}


def evidence_packet(connection, summary_id: str, project_id: str, skill: str, rules: list[dict]) -> dict:
    if any(rule.get("sourceIdsTruncated") for rule in rules):
        raise ValueError("candidate source IDs are truncated; use complete Summary lineage")
    ids = {source for rule in rules for source in rule.get("sourceRecordIds", [])}
    rows = connection.execute(
        """SELECT r.id, r.run_id, r.captured_at, r.output_json, r.edited_content,
                  r.review_note, r.is_classic
           FROM learning_records r JOIN learning_summary_sources s ON s.record_id = r.id
           WHERE s.summary_id = ? AND r.project_id = ? AND r.skill = ?
           ORDER BY r.captured_at, r.id""", (summary_id, project_id, skill),
    ).fetchall()
    records = []
    available = {row["id"] for row in rows}
    if not ids.issubset(available):
        raise ValueError("Summary candidates reference missing source records")
    for row in rows:
        if row["id"] not in ids:
            continue
        raw = row["edited_content"] or row["output_json"]
        try:
            content = json.loads(raw)
        except (ValueError, TypeError):
            content = raw
        item = {"recordId": row["id"], "runId": row["run_id"],
                "capturedAt": row["captured_at"], "reviewNote": row["review_note"],
                "classic": bool(row["is_classic"]), "effectiveContent": content}
        if len(json.dumps(item, ensure_ascii=False).encode("utf-8")) > MAX_RECORD_BYTES:
            raise ValueError("source record exceeds the Summary evidence budget; review or shorten it first")
        records.append(item)
    packet = {"skill": skill, "skillCriteria": SKILL_CRITERIA.get(skill,
              "Keep only reusable changes to this Skill's behavior, not task-specific answers."),
              "candidates": rules, "records": records}
    if len(json.dumps(packet, ensure_ascii=False).encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise ValueError("Summary evidence exceeds the 48 KB evaluation budget")
    return packet
