#!/usr/bin/env python3
"""Compare a frozen skill-evaluation baseline with a fixed-case candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FAILURE_STATUSES = {"backend_unavailable", "runner_error", "safety_failure", "timeout"}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def results_by_case(run: dict, label: str) -> dict[str, dict]:
    results = run.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{label}.results must be an array")
    by_case = {}
    for result in results:
        case_id = result.get("case_id") if isinstance(result, dict) else None
        if not isinstance(case_id, str):
            raise ValueError(f"{label} result must contain a string case_id")
        if case_id in by_case:
            raise ValueError(f"{label} contains duplicate case: {case_id}")
        by_case[case_id] = result
    return by_case


def verify_baseline_artifacts(baseline_dir: Path, manifest: dict) -> None:
    hashes = manifest.get("artifact_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("baseline manifest must contain artifact_hashes")
    root = baseline_dir.resolve()
    for relative, expected_hash in hashes.items():
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError("baseline artifact hashes must map string paths to hashes")
        artifact = (root / relative).resolve()
        if not artifact.is_relative_to(root) or not artifact.is_file():
            raise ValueError(f"baseline artifact is missing or escapes the baseline: {relative}")
        if sha256(artifact) != expected_hash:
            raise ValueError(f"baseline artifact hash mismatch: {relative}")


def quality_map(run: dict) -> dict[str, str] | None:
    results = run.get("results", [])
    if not results or any(result.get("gate") not in {"pass", "fail"} for result in results):
        return None
    return {result["case_id"]: result["gate"] for result in results}


def compare(baseline_dir: Path, candidate_path: Path) -> dict:
    manifest = load_json(baseline_dir / "baseline.json")
    verify_baseline_artifacts(baseline_dir, manifest)
    baseline_path = baseline_dir / "scored.json" if (baseline_dir / "scored.json").is_file() else baseline_dir / "run.json"
    baseline = load_json(baseline_path)
    candidate = load_json(candidate_path)
    expected_corpus = manifest.get("corpus_sha256")
    if not isinstance(expected_corpus, str):
        raise ValueError("baseline manifest must contain corpus_sha256")
    if baseline.get("corpus_sha256") != expected_corpus:
        raise ValueError("baseline run corpus does not match its manifest")
    if candidate.get("corpus_sha256") != expected_corpus:
        raise ValueError("candidate corpus does not match the frozen baseline")
    baseline_results = results_by_case(baseline, "baseline")
    candidate_results = results_by_case(candidate, "candidate")
    expected = set(manifest["case_ids"])
    if set(baseline_results) != expected:
        raise ValueError("frozen baseline run does not match its manifest case set")
    if set(candidate_results) != expected:
        missing = sorted(expected - set(candidate_results))
        extra = sorted(set(candidate_results) - expected)
        raise ValueError(f"candidate case mismatch; missing={missing}, extra={extra}")

    cases = []
    for case_id in manifest["case_ids"]:
        before = baseline_results[case_id]
        after = candidate_results[case_id]
        baseline_ms = before.get("duration_ms", 0)
        candidate_ms = after.get("duration_ms", 0)
        cases.append({
            "case_id": case_id,
            "baseline_status": before.get("status"),
            "candidate_status": after.get("status"),
            "execution_regression": after.get("status") in FAILURE_STATUSES and before.get("status") not in FAILURE_STATUSES,
            "baseline_duration_ms": baseline_ms,
            "candidate_duration_ms": candidate_ms,
            "duration_delta_ms": candidate_ms - baseline_ms,
        })
    baseline_quality = quality_map(baseline)
    candidate_quality = quality_map(candidate)
    quality_available = baseline_quality is not None and candidate_quality is not None
    regressions = [] if not quality_available else [
        case_id for case_id in manifest["case_ids"]
        if baseline_quality[case_id] == "pass" and candidate_quality[case_id] == "fail"
    ]
    execution_regressions = [case["case_id"] for case in cases if case["execution_regression"]]
    baseline_total = sum(case["baseline_duration_ms"] for case in cases)
    candidate_total = sum(case["candidate_duration_ms"] for case in cases)
    return {
        "schema_version": 1,
        "baseline_label": manifest["label"],
        "case_count": len(cases),
        "case_parity": True,
        "execution": {
            "regressions": execution_regressions,
            "ok": not execution_regressions,
        },
        "quality": {
            "status": "compared" if quality_available else "unavailable_pending_human_scoring",
            "regressions": regressions,
            "ok": not regressions if quality_available else None,
        },
        "latency": {
            "baseline_total_ms": baseline_total,
            "candidate_total_ms": candidate_total,
            "delta_ms": candidate_total - baseline_total,
            "delta_percent": None if baseline_total == 0 else round((candidate_total - baseline_total) * 100 / baseline_total, 2),
        },
        "gate_decision": (
            "fail" if execution_regressions
            else "pass" if quality_available and not regressions
            else "fail" if quality_available
            else "pending_human_scoring"
        ),
        "cases": cases,
    }


def markdown(report: dict) -> str:
    lines = [
        "# Skill Evaluation Comparison",
        "",
        f"- Baseline: `{report['baseline_label']}`",
        f"- Fixed cases: {report['case_count']}",
        f"- Execution regressions: {len(report['execution']['regressions'])}",
        f"- Quality: `{report['quality']['status']}`",
        f"- Latency delta: {report['latency']['delta_ms']} ms ({report['latency']['delta_percent']}%)",
        f"- Gate decision: `{report['gate_decision']}`",
        "",
        "| Case | Baseline | Candidate | Delta ms | Execution regression |",
        "|---|---|---|---:|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| `{case['case_id']}` | `{case['baseline_status']}` | `{case['candidate_status']}` | "
            f"{case['duration_delta_ms']} | {'yes' if case['execution_regression'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = compare(args.baseline.resolve(), args.candidate.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"error: {error}") from None
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "comparison.md").write_text(markdown(report), encoding="utf-8")
    print(f"Skill eval comparison: gate={report['gate_decision']}, cases={report['case_count']}.")
    return 1 if report["gate_decision"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
