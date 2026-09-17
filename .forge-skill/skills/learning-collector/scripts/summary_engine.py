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

_TEXT_KEYS = (
    "instruction", "recommendation", "action", "step", "description",
    "summary", "title", "name", "value",
)

_GENERIC_TOPIC_TERMS = {
    "check", "incorrect", "issue", "missing", "problem", "result",
    "failure", "failed", "handling", "implementation", "validation",
}

_SPECIALIZED_PROFILES = {
    "debug": (
        (("fix", "fixes", "remediation", "correctiveAction", "nextDiagnosticStep"),
         ("rootCause", "diagnosis", "symptom"), ("rootCause", "evidence"), "PRE_CHECK", "DIAGNOSTIC_CORRECTION"),
        (("verification", "verificationPlan", "validation"),
         ("rootCause", "diagnosis"), ("evidence", "openQuestions"), "FINAL_VALIDATION", "VERIFY_DIAGNOSIS"),
        (("rootCause", "diagnosis"),
         ("symptom",), ("evidence",), "PRE_CHECK", "ROOT_CAUSE_CANDIDATE"),
    ),
    "implement": (
        (("changes", "implementation", "decisions", "approach", "edgeCases"),
         ("scope", "objective"), ("constraints", "rationale"), "PRE_CHECK", "IMPLEMENTATION_ADJUSTMENT"),
        (("verification", "validation", "tests"),
         ("scope", "objective"), ("remainingRisk", "residualRisk", "caveats"), "FINAL_VALIDATION", "VERIFY_IMPLEMENTATION"),
    ),
    "page-test": (
        (("fix", "fixes", "testCases", "scenarios", "locatorStrategy", "waitStrategy", "assertions"),
         ("symptom", "rootCause", "scope"), ("evidence", "rootCause"), "PRE_CHECK", "PAGE_TEST_ADJUSTMENT"),
        (("verification", "executionResults", "residualRisk"),
         ("scope", "symptom"), ("environment", "caveats"), "FINAL_VALIDATION", "VERIFY_PAGE_TEST"),
    ),
    "test-implementation": (
        (("tests", "testCases", "scenarios", "assertions", "edgeCases"),
         ("testScope", "scope", "targetBehavior"), ("risk", "rationale"), "PRE_CHECK", "TEST_COVERAGE_ADJUSTMENT"),
        (("verification", "coverageGaps", "remainingCoverage", "uncovered"),
         ("testScope", "scope"), ("limitations", "risk"), "FINAL_VALIDATION", "VERIFY_TEST_COVERAGE"),
    ),
    "refactor": (
        (("structuralProblems", "transformations", "steps", "targetStructure", "refactoring"),
         ("objective", "currentState"), ("evidence", "whyItMatters"), "PRE_CHECK", "REFACTOR_ADJUSTMENT"),
        (("behaviorPreservation", "validation", "verification", "risks"),
         ("objective", "targetStructure"), ("currentState", "constraints"), "FINAL_VALIDATION", "VERIFY_REFACTOR"),
    ),
    "explain": (
        (("corrections", "misconceptions", "commonPitfalls", "pitfalls", "tradeoffs"),
         ("concept", "topic", "whatItIs"), ("whyItMatters", "example"), "FINAL_VALIDATION", "EXPLANATION_ADJUSTMENT"),
        (("keyPoints", "mentalModel"),
         ("concept", "topic"), ("whyItMatters",), "PRE_CHECK", "EXPLANATION_CANDIDATE"),
    ),
    "plan": (
        (("constraints", "assumptions", "steps", "implementationSteps", "phases", "dependencies"),
         ("objective", "scope"), ("approach", "rationale"), "PRE_CHECK", "PLAN_ADJUSTMENT"),
        (("risks", "mitigations", "validationPlan", "verification"),
         ("objective", "scope"), ("constraints", "assumptions"), "FINAL_VALIDATION", "VERIFY_PLAN"),
    ),
    "explore": (
        (("constraints", "observations", "options", "directions", "decisionCriteria", "evidenceNeeded"),
         ("currentUnderstanding", "goal", "scope"), ("unknowns", "openQuestions"), "PRE_CHECK", "EXPLORATION_CANDIDATE"),
        (("recommendedNextStep", "nextStep"),
         ("goal", "scope"), ("decisionCriteria", "evidenceNeeded"), "FINAL_VALIDATION", "VERIFY_EXPLORATION"),
    ),
}


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
    if left.get("stage") and right.get("stage") and left["stage"] != right["stage"]:
        return False
    title_score = _similarity(left, right)
    if title_score == 1.0:
        left_direction = _normalize(_text(left.get("direction")))
        right_direction = _normalize(_text(right.get("direction")))
        if left_direction == right_direction:
            return True
        negation = ("不要", "不应", "不得", "禁止", "never", "don't", "do not", "must not")
        left_negative = any(term in _text(left.get("direction")).lower() for term in negation)
        right_negative = any(term in _text(right.get("direction")).lower() for term in negation)
        if left_negative != right_negative:
            return False
        # Treat common opposite actions as a conflict even when neither side
        # uses an explicit negation word.
        opposite_pairs = (
            ("increase", "decrease"), ("enable", "disable"),
            ("allow", "deny"), ("add", "remove"), ("include", "exclude"),
            ("增加", "减少"), ("启用", "停用"), ("允许", "禁止"),
            ("添加", "删除"), ("纳入", "排除"),
        )
        left_text = _text(left.get("direction")).lower()
        right_text = _text(right.get("direction")).lower()
        if any((a in left_text and b in right_text) or (b in left_text and a in right_text)
               for a, b in opposite_pairs):
            return False
        return _direction_similarity(left, right) >= 0.55
    left_terms = {
        term for term in re.findall(r"[a-z][a-z0-9_.-]{2,}", _text(left.get("title")).lower())
        if term not in _GENERIC_TOPIC_TERMS
    }
    right_terms = {
        term for term in re.findall(r"[a-z][a-z0-9_.-]{2,}", _text(right.get("title")).lower())
        if term not in _GENERIC_TOPIC_TERMS
    }
    if left_terms and right_terms and not left_terms.intersection(right_terms):
        return False
    return title_score >= 0.55 or (
        title_score >= 0.24 and _direction_similarity(left, right) >= 0.35
    )


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
    stage = representative.get("stage") or stage
    rule_type = representative.get("type") or rule_type
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


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(container: dict, aliases: tuple[str, ...]):
    wanted = {_key(alias) for alias in aliases}
    for name, value in container.items():
        if _key(name) in wanted:
            return value
    return None


def _fields(container: dict, aliases: tuple[str, ...]) -> list:
    wanted = {_key(alias) for alias in aliases}
    return [value for name, value in container.items() if _key(name) in wanted]


def _candidate_texts(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [text for item in value for text in _candidate_texts(item)]
    if isinstance(value, dict):
        texts = []
        for alias in _TEXT_KEYS:
            selected = _field(value, (alias,))
            if selected is not None:
                texts.extend(_candidate_texts(selected))
        return list(dict.fromkeys(texts))
    return []


def _first_text(container: dict, aliases: tuple[str, ...]) -> str:
    texts = _candidate_texts(_field(container, aliases))
    return texts[0] if texts else ""


def _containers(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _containers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _containers(child)


def _profile_candidates(record: dict, profile: tuple) -> list[dict]:
    content = record.get("content")
    if isinstance(content, str) and content.strip():
        text = _clip(content, MAX_INSTRUCTION_CHARS)
        return [{
            "sourceRecordId": record["recordId"], "runId": record.get("runId") or record["recordId"], "capturedAt": record.get("capturedAt", ""),
            "title": text, "direction": text, "impact": _text(record.get("reviewNote")),
            "severity": "UNSPECIFIED", "confidence": "LOW", "stage": "FINAL_VALIDATION",
            "type": "HUMAN_REVIEWED_CANDIDATE", "reviewNote": _text(record.get("reviewNote")),
        }]
    if not isinstance(content, dict):
        return []
    candidates = []
    seen = set()
    root_context = _first_text(content, ("objective", "scope", "topic", "concept", "overallAssessment"))
    for container in _containers(content):
        signals = _field(container, ("learningSignals",))
        if isinstance(signals, list):
            for signal in signals:
                if not isinstance(signal, dict):
                    continue
                instruction = _first_text(signal, ("instruction", "recommendation", "action"))
                normalized = _normalize(instruction)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                stage = str(signal.get("stage") or "FINAL_VALIDATION").upper()
                if stage not in {"PRE_CHECK", "FINAL_VALIDATION"}:
                    stage = "FINAL_VALIDATION"
                candidates.append({
                    "sourceRecordId": record["recordId"], "runId": record.get("runId") or record["recordId"], "capturedAt": record.get("capturedAt", ""),
                    "title": _first_text(signal, ("title",)) or instruction,
                    "direction": instruction,
                    "impact": _first_text(signal, ("rationale", "evidence", "whyItMatters")),
                    "severity": "UNSPECIFIED", "confidence": "LOW", "stage": stage,
                    "type": "LEARNING_SIGNAL", "reviewNote": _text(record.get("reviewNote")),
                })
        for instruction_keys, title_keys, rationale_keys, stage, rule_type in profile:
            context = _first_text(container, title_keys) or root_context
            rationale = _first_text(container, rationale_keys) or context
            for value in _fields(container, instruction_keys):
                for instruction in _candidate_texts(value):
                    normalized = _normalize(instruction)
                    if not normalized or normalized in seen:
                        continue
                    seen.add(normalized)
                    candidates.append({
                        "sourceRecordId": record["recordId"], "runId": record.get("runId") or record["recordId"], "capturedAt": record.get("capturedAt", ""),
                        "title": instruction, "direction": instruction, "impact": rationale,
                        "severity": "UNSPECIFIED", "confidence": "LOW", "stage": stage,
                        "type": rule_type, "reviewNote": _text(record.get("reviewNote")),
                    })
    return candidates


def build_specialized_summary(records: list[dict], *, skill: str, max_rules: int = MAX_RULES) -> dict:
    """Extract Skill-specific, evidence-bound candidates without semantic invention."""
    profile = _SPECIALIZED_PROFILES[skill]
    candidates = [candidate for record in records for candidate in _profile_candidates(record, profile)]
    all_clusters = _cluster(candidates)
    clusters = [group for group in all_clusters if (
        any(item["type"] == "LEARNING_SIGNAL" or item["reviewNote"] for item in group)
        or len({item["runId"] for item in group}) >= 2
    )]
    clusters.sort(key=lambda group: (
        len({item["runId"] for item in group}), max(item["capturedAt"] for item in group)
    ), reverse=True)
    rules = [_rule(cluster, index + 1) for index, cluster in enumerate(clusters[:max_rules])]
    for rule, cluster in zip(rules, clusters):
        independent = len({item["runId"] for item in cluster})
        rule["confidence"] = "HIGH" if independent >= 3 else "MEDIUM" if independent == 2 else "LOW"
    records_with_signals = len({item["sourceRecordId"] for item in candidates})
    return {
        "status": "DRAFT", "statistics": {
            "eligibleRecords": len(records), "emptySignalResults": len(records) - records_with_signals,
            "originalFindings": len(candidates), "candidateClusters": len(clusters),
            "generatedRules": len(rules), "lowEvidenceClusters": len(all_clusters) - len(clusters),
            "discardedClusters": max(0, len(clusters) - len(rules)),
        }, "rules": rules, "quality": {
            "summarizer": f"{skill}-deterministic-v1", "ruleLimit": max_rules,
            "semanticInference": False,
            "limitations": [
                "Only Skill-specific structured fields and explicit learningSignals are extracted.",
                "Ordinary output candidates require two independent records unless explicitly marked by a learningSignal or human review note.",
                "Candidates preserve source wording and remain PENDING until human or explicit LLM refinement.",
                "Lexical similarity may leave semantic duplicates separate or merge close wording; review is required.",
            ],
        },
    }


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
    if skill in _SPECIALIZED_PROFILES:
        return build_specialized_summary(records, skill=skill, max_rules=max_rules)
    return build_generic_summary(records, skill=skill, max_rules=max_rules)
