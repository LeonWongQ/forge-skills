"""Evidence and output gates for explicit, project-scoped Summary refinement."""
from __future__ import annotations

import json
import unicodedata

MAX_EVIDENCE_BYTES = 48_000
MAX_RECORD_BYTES = 16_000
MAX_REFINED_RULES = 6

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
        raise ValueError("candidate source IDs are truncated; narrow the Summary before refinement")
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
            raise ValueError("source record exceeds the refinement evidence budget; review or shorten it first")
        records.append(item)
    packet = {"skill": skill, "skillCriteria": SKILL_CRITERIA.get(skill,
              "Keep only reusable changes to this Skill's behavior, not task-specific answers."),
              "candidates": rules, "records": records}
    if len(json.dumps(packet, ensure_ascii=False).encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise ValueError("refinement evidence exceeds the 48 KB budget; create a narrower Summary")
    return packet


def validate_decisions(value: object, rules: list[dict]) -> tuple[list[dict], list[dict]]:
    if not isinstance(value, dict) or not isinstance(value.get("decisions"), list):
        raise ValueError("LLM returned invalid candidate decisions")
    expected = {rule["id"] for rule in rules}
    decisions = value["decisions"]
    ids = [item.get("candidateId") for item in decisions if isinstance(item, dict)]
    if (len(ids) != len(decisions) or any(not isinstance(item, str) for item in ids)
            or len(decisions) != len(rules) or len(set(ids)) != len(ids) or set(ids) != expected):
        raise ValueError("LLM must classify every candidate exactly once")
    for item in decisions:
        if item.get("decision") not in {"KEEP", "DISCARD", "CONFLICT"}:
            raise ValueError("LLM returned invalid candidate decision")
        reason = item.get("reason")
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 240:
            raise ValueError("LLM returned invalid decision reason")
    retained = [item for item in decisions if item["decision"] == "KEEP"]
    return retained, decisions


def _normalized(text: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKC", text).casefold()
                   if character.isalnum())


def validate_rules(value: object, retained: list[dict], candidates: list[dict], records: list[dict]) -> list[dict]:
    rules = value.get("rules") if isinstance(value, dict) else None
    if not isinstance(rules, list) or len(rules) > MAX_REFINED_RULES:
        raise ValueError("LLM returned invalid rules (maximum six)")
    allowed = {item["candidateId"] for item in retained}
    by_id = {item["id"]: item for item in candidates}
    by_record = {item["recordId"]: item for item in records}
    used_ids, used_instructions = set(), set()
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str) or not rule["id"].strip() or rule["id"] in used_ids:
            raise ValueError("LLM returned duplicate or invalid rule IDs")
        used_ids.add(rule["id"])
        if rule.get("status") != "PENDING" or rule.get("stage") not in {"PRE_CHECK", "FINAL_VALIDATION"}:
            raise ValueError("LLM may only return pending valid stages")
        if not isinstance(rule.get("type"), str) or not rule["type"].strip():
            raise ValueError("LLM returned invalid rule type")
        for key, limit in (("title", 100), ("trigger", 200), ("instruction", 500),
                           ("verification", 300), ("rationale", 300)):
            field = rule.get(key)
            if not isinstance(field, str) or not 1 <= len(field.strip()) <= limit:
                raise ValueError(f"LLM returned invalid {key}")
            if "\ufffd" in field or any("\ud800" <= char <= "\udfff" for char in field):
                raise ValueError("LLM returned damaged Unicode text")
        anti_pattern = rule.get("antiPattern", "")
        if not isinstance(anti_pattern, str) or len(anti_pattern) > 300:
            raise ValueError("LLM returned invalid antiPattern")
        if "\ufffd" in anti_pattern or any("\ud800" <= char <= "\udfff" for char in anti_pattern):
            raise ValueError("LLM returned damaged Unicode text")
        candidate_ids, source_ids = rule.get("candidateIds"), rule.get("sourceRecordIds")
        if (not isinstance(candidate_ids, list) or not candidate_ids or
                any(not isinstance(item, str) for item in candidate_ids) or
                len(set(candidate_ids)) != len(candidate_ids) or not set(candidate_ids) <= allowed):
            raise ValueError("LLM returned unapproved candidate IDs")
        supported = {source for candidate_id in candidate_ids for source in by_id[candidate_id]["sourceRecordIds"]}
        if (not isinstance(source_ids, list) or not source_ids or
                any(not isinstance(item, str) for item in source_ids) or
                len(set(source_ids)) != len(source_ids) or not set(source_ids) <= supported or
                not set(source_ids) <= set(by_record)):
            raise ValueError("LLM returned unknown source IDs")
        normalized = (rule["stage"], _normalized(rule["instruction"]))
        if normalized in used_instructions:
            raise ValueError("LLM returned duplicate instructions")
        used_instructions.add(normalized)
        independent_runs = {by_record[source]["runId"] or source for source in source_ids}
        human_confirmed = any(by_record[source]["reviewNote"] for source in source_ids)
        rule["confidence"] = "HIGH" if len(independent_runs) >= 3 else "MEDIUM" if len(independent_runs) >= 2 or human_confirmed else "LOW"
        rule["supportCount"] = len(source_ids)
    return rules
