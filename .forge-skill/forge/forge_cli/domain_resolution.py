# -*- coding: utf-8 -*-
"""Conservative, evidence-backed runtime domain refinement."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .helpers import normalize_text
from .registry_discovery import load_array_registry


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def _matches(text: str, value: str) -> bool:
    normalized = normalize_text(value)
    return bool(normalized) and normalized in text


def resolve_domains(
    root,
    eligible_domains: Iterable[str],
    request_text: str = "",
    artifact_evidence: Any = None,
    protected_domains: Iterable[str] = (),
) -> Dict[str, Any]:
    """Refine eligible domains without changing routing selection semantics."""
    entries = {item.get("id"): item for item in load_array_registry(root, "domains.json", ["domains"]) if isinstance(item, dict)}
    eligible = _unique(eligible_domains)
    protected = _unique(protected_domains)
    text = normalize_text(request_text)
    artifacts = artifact_evidence if isinstance(artifact_evidence, list) else []
    artifact_text = normalize_text(" ".join(str(item) for item in artifacts))
    evidence: List[Dict[str, Any]] = []
    selected: List[str] = []
    rejected: List[Dict[str, Any]] = []

    for domain_id in eligible:
        entry = entries.get(domain_id)
        if not entry:
            rejected.append({"domain_id": domain_id, "reason": "unknown_domain"})
            continue
        matches: List[Dict[str, Any]] = []
        for alias in entry.get("aliases", []):
            if isinstance(alias, str) and _matches(text, alias):
                matches.append({"source": "request_alias", "matched": alias, "score": 2})
        signals = entry.get("activation_signals", {})
        for signal in signals.get("request_signals", []) if isinstance(signals, dict) else []:
            if isinstance(signal, str) and _matches(text, signal):
                matches.append({"source": "request_signal", "matched": signal, "score": 3})
        for signal in signals.get("artifact_signals", []) if isinstance(signals, dict) else []:
            if isinstance(signal, str) and _matches(artifact_text, signal):
                matches.append({"source": "artifact_signal", "matched": signal, "score": 4})
        if domain_id in protected:
            matches.append({"source": "protected_selection", "matched": domain_id, "score": 1})
        if matches:
            selected.append(domain_id)
            for match in matches:
                evidence.append({"domain_id": domain_id, **match})
        else:
            rejected.append({"domain_id": domain_id, "reason": "no_direct_evidence"})

    # Preserve selected baseline when request evidence is absent, making fallback explicit.
    warnings: List[str] = []
    if not selected and eligible:
        selected = eligible
        warnings.append("No direct domain evidence; retained eligible domains as a conservative fallback")
        for domain_id in selected:
            evidence.append({"domain_id": domain_id, "source": "eligible_fallback", "matched": domain_id, "score": 0})

    # Related domains require corroborating direct request/artifact evidence.
    considered: List[Dict[str, Any]] = []
    for domain_id in list(selected):
        for related in entries.get(domain_id, {}).get("related_domains", []):
            if related in selected or related not in entries:
                continue
            related_entry = entries[related]
            markers = list(related_entry.get("aliases", []))
            signals = related_entry.get("activation_signals", {})
            if isinstance(signals, dict):
                markers += list(signals.get("request_signals", [])) + list(signals.get("artifact_signals", []))
            corroborated = next((marker for marker in markers if isinstance(marker, str) and (_matches(text, marker) or _matches(artifact_text, marker))), None)
            if corroborated:
                selected.append(related)
                evidence.append({"domain_id": related, "source": "related_corroborated", "matched": corroborated, "score": 1, "parent_domain": domain_id})
                considered.append({"domain_id": related, "parent_domain": domain_id, "accepted": True})
            else:
                considered.append({"domain_id": related, "parent_domain": domain_id, "accepted": False, "reason": "no_corroboration"})

    return {
        "eligible_domains": eligible,
        "protected_domains": protected,
        "selected_domains": _unique(selected),
        "evidence": evidence,
        "rejected": rejected,
        "related_candidates": considered,
        "confidence": "medium" if any(item["source"] != "eligible_fallback" for item in evidence) else "low",
        "warnings": warnings,
    }
