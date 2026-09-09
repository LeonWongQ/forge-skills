"""Deterministic, evidence-bound Skill training summary builders."""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone

MAX_RULES = 12
MAX_INSTRUCTION_CHARS = 240
MAX_RATIONALE_CHARS = 180
MAX_VISIBLE_SOURCE_IDS = 20

_SEVERITY_WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
_FINAL_TERMS = (
    "误报", "漏报", "严重级别", "置信度", "证据", "输出", "结论", "报告",
    "false positive", "false negative", "severity", "confidence", "evidence", "output",
)


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clip(value: str, limit: int) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"(?:[a-z]:)?[/\\][\w ._\-/\\]+", " path ", value)
    value = re.sub(r"\b\d+(?:[-:.]\d+)*\b", " n ", value)
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def _ngrams(value: str, size: int = 2) -> set[str]:
    normalized = _normalize(value)
    return {normalized[index:index + size] for index in range(max(0, len(normalized) - size + 1))}


def _similarity(left: dict, right: dict) -> float:
    left_title, right_title = _text(left.get("title")), _text(right.get("title"))
    left_norm, right_norm = _normalize(left_title), _normalize(right_title)
    if left_norm and left_norm == right_norm:
        return 1.0
    sequence = difflib.SequenceMatcher(None, left_norm, right_norm).ratio()
    left_grams, right_grams = _ngrams(left_title), _ngrams(right_title)
    union = left_grams | right_grams
    jaccard = len(left_grams & right_grams) / len(union) if union else 0.0
    left_terms = set(re.findall(r"[a-z][a-z0-9_.-]{2,}", left_title.lower()))
    right_terms = set(re.findall(r"[a-z][a-z0-9_.-]{2,}", right_title.lower()))
    technical = len(left_terms & right_terms) / max(1, min(len(left_terms), len(right_terms)))
    return sequence * 0.55 + jaccard * 0.35 + technical * 0.10


def _direction_similarity(left: dict, right: dict) -> float:
    return difflib.SequenceMatcher(
        None, _normalize(_text(left.get("direction"))), _normalize(_text(right.get("direction")))
    ).ratio()


def _same_topic(left: dict, right: dict) -> bool:
    title_score = _similarity(left, right)
    return title_score >= 0.25 or (title_score >= 0.195 and _direction_similarity(left, right) >= 0.19)


def _extract_findings(records: list[dict]) -> tuple[list[dict], int]:
    findings: list[dict] = []
    empty_results = 0
    for record in records:
        content = record.get("content")
        values = content.get("findings") if isinstance(content, dict) else None
        if not isinstance(values, list) or not values:
            empty_results += 1
            continue
        for finding in values:
            if not isinstance(finding, dict) or not _text(finding.get("title")):
                continue
            findings.append({
                "sourceRecordId": record["recordId"],
                "capturedAt": record.get("capturedAt", ""),
                "title": _text(finding.get("title")),
                "severity": _text(finding.get("severity")).upper() or "UNSPECIFIED",
                "direction": _text(finding.get("direction") or finding.get("suggested_direction")),
                "impact": _text(finding.get("impact") or finding.get("why_it_matters")),
                "confidence": _text(finding.get("confidence")).upper(),
                "reviewNote": _text(record.get("reviewNote")),
            })
    return findings, empty_results


def _cluster(findings: list[dict]) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for finding in findings:
        best_index, best_score = None, 0.0
        for index, cluster in enumerate(clusters):
            matching = [existing for existing in cluster if _same_topic(finding, existing)]
            score = max((_similarity(finding, existing) + _direction_similarity(finding, existing)
                         for existing in matching), default=0.0)
            if score > best_score:
                best_index, best_score = index, score
        if best_index is not None:
            clusters[best_index].append(finding)
        else:
            clusters.append([finding])
    return clusters


def _representative(cluster: list[dict]) -> dict:
    return max(cluster, key=lambda item: (
        sum(_similarity(item, other) + _direction_similarity(item, other) for other in cluster),
        _SEVERITY_WEIGHT.get(item["severity"], 0), bool(item["direction"]), item["capturedAt"],
    ))


def _instruction(finding: dict) -> str:
    direction = finding["direction"]
    if direction:
        first = re.split(r"(?<=[。！？.!?])\s*", direction, maxsplit=1)[0]
        return _clip(first, MAX_INSTRUCTION_CHARS)
    return _clip(f"检查是否存在“{finding['title']}”，仅在当前证据充分时报告。", MAX_INSTRUCTION_CHARS)


def _stage(finding: dict) -> tuple[str, str]:
    value = f"{finding['title']} {finding['direction']}".lower()
    if any(term in value for term in _FINAL_TERMS):
        return "FINAL_VALIDATION", "VALIDATE_OUTPUT"
    return "PRE_CHECK", "ADD_CHECK"


def _rule(cluster: list[dict], index: int) -> dict:
    representative = _representative(cluster)
    source_ids = list(dict.fromkeys(item["sourceRecordId"] for item in cluster))
    stage, rule_type = _stage(representative)
    digest = hashlib.sha256("\0".join(sorted(source_ids)).encode("utf-8")).hexdigest()[:10]
    severities = {item["severity"] for item in cluster}
    return {
        "id": f"rule-{index:03d}-{digest}",
        "stage": stage,
        "type": rule_type,
        "title": _clip(representative["title"], 100),
        "instruction": _instruction(representative),
        "rationale": _clip(representative["impact"], MAX_RATIONALE_CHARS),
        "status": "PENDING",
        "supportCount": len(source_ids),
        "sourceRecordIds": source_ids[:MAX_VISIBLE_SOURCE_IDS],
        "sourceIdsTruncated": len(source_ids) > MAX_VISIBLE_SOURCE_IDS,
        "severitySignals": sorted(severities, key=lambda value: -_SEVERITY_WEIGHT.get(value, 0)),
        "confidence": "HIGH" if len(source_ids) >= 3 else "MEDIUM" if len(source_ids) == 2 else "LOW",
    }


def build_code_review_summary(records: list[dict]) -> dict:
    """Create compact rule candidates from reviewed ACTIVE code-review results."""
    findings, empty_results = _extract_findings(records)
    clusters = _cluster(findings)
    clusters.sort(key=lambda group: (
        len({item["sourceRecordId"] for item in group}),
        max(_SEVERITY_WEIGHT.get(item["severity"], 0) for item in group),
        max(item["capturedAt"] for item in group),
    ), reverse=True)
    selected = clusters[:MAX_RULES]
    rules = [_rule(cluster, index + 1) for index, cluster in enumerate(selected)]
    return {
        "status": "DRAFT",
        "statistics": {
            "eligibleRecords": len(records),
            "emptyFindingResults": empty_results,
            "originalFindings": len(findings),
            "candidateClusters": len(clusters),
            "generatedRules": len(rules),
            "discardedClusters": max(0, len(clusters) - len(rules)),
        },
        "rules": rules,
        "quality": {
            "summarizer": "code-review-deterministic-v1",
            "ruleLimit": MAX_RULES,
            "semanticInference": False,
            "limitations": [
                "Similarity is lexical and technical-token based; review merged and unmerged rules manually.",
                "Historical disappearance does not prove that a finding was fixed.",
                "All generated rules remain PENDING until reviewed by a person.",
            ],
        },
    }


def encoded_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _generic_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("conclusion", "overallAssessment", "assessment", "instruction", "recommendation", "summary"):
            text = _generic_text(value.get(key))
            if text:
                return text
        return ""
    return ""


def build_generic_summary(records: list[dict], *, skill: str, max_rules: int = MAX_RULES) -> dict:
    """Build reviewable candidates for Skills without a specialized extractor.

    This is intentionally an evidence-preserving fallback, not semantic summarization.
    An explicit LLM refinement step may replace these candidates before review.
    """
    rules = []
    for index, record in enumerate(records[:max_rules], 1):
        content = record.get("content")
        text = _clip(_generic_text(content), MAX_INSTRUCTION_CHARS)
        if not text:
            continue
        digest = hashlib.sha256(str(record.get("recordId", "")).encode("utf-8")).hexdigest()[:10]
        rules.append({
            "id": f"rule-{index:03d}-{digest}", "stage": "FINAL_VALIDATION",
            "type": "REVIEW_CANDIDATE", "title": _clip(text, 100),
            "instruction": text, "rationale": "来自人工审核后的 Skill 结果，待提炼。",
            "status": "PENDING", "supportCount": 1,
            "sourceRecordIds": [record.get("recordId")], "sourceIdsTruncated": False,
            "severitySignals": [], "confidence": "LOW",
        })
    return {
        "status": "DRAFT", "statistics": {
            "eligibleRecords": len(records), "originalFindings": len(records),
            "candidateClusters": len(rules), "generatedRules": len(rules),
            "discardedClusters": max(0, len(records) - len(rules)),
        }, "rules": rules, "quality": {
            "summarizer": "generic-evidence-candidate-v1", "semanticInference": False,
            "limitations": ["该 Skill 没有专用提炼器；候选内容保留原意，需人工或显式 LLM 提炼。"],
        },
    }


def build_summary(records: list[dict], *, skill: str, max_rules: int = MAX_RULES) -> dict:
    if skill == "code-review":
        return build_code_review_summary(records)
    return build_generic_summary(records, skill=skill, max_rules=max_rules)
