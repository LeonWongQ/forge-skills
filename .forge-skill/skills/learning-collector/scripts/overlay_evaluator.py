"""LLM-backed baseline/candidate evaluation for project Skill overlays."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import uuid
from pathlib import Path
from typing import Callable


EVALUATION_FORMAT = "forge-overlay-behavior-evaluation-v1"
GATE_VERSION = "user-approved-default-v1"
MAX_FIXTURE_BYTES = 128 * 1024
MIN_EVALUATION_CASES = 3


def _compatible_cases(corpus: object, skill: str) -> list[dict]:
    if not isinstance(corpus, dict) or not isinstance(corpus.get("cases"), list):
        return []
    return [
        case for case in corpus.get("cases", [])
        if (isinstance(case, dict) and case.get("skill") == skill
            and case.get("execution", {}).get("mode") == "automated"
            and case.get("execution", {}).get("sandbox") == "read-only"
            and set(case.get("execution", {}).get("requires_capabilities", [])) <= {"filesystem_read"})
    ]


def evaluation_readiness(forge_root: Path, skill: str) -> dict:
    """Describe whether a Skill has enough compatible fixed cases to run the gate."""
    corpus_path = forge_root / "evals" / "skill-behavior-cases.json"
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        cases = _compatible_cases(corpus, skill)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as error:
        return {
            "ready": False,
            "caseCount": 0,
            "requiredCaseCount": MIN_EVALUATION_CASES,
            "categories": [],
            "missingCaseCount": MIN_EVALUATION_CASES,
            "error": f"evaluation corpus unavailable: {type(error).__name__}",
        }
    count = len(cases)
    return {
        "ready": count >= MIN_EVALUATION_CASES,
        "caseCount": count,
        "requiredCaseCount": MIN_EVALUATION_CASES,
        "categories": sorted({str(case.get("category")) for case in cases if case.get("category")}),
        "missingCaseCount": max(0, MIN_EVALUATION_CASES - count),
    }


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_runner(forge_root: Path):
    runner_path = forge_root / "scripts" / "run-skill-evals.py"
    spec = importlib.util.spec_from_file_location("forge_skill_eval_runner", runner_path)
    if spec is None or spec.loader is None:
        raise ValueError("Skill evaluation fixture runner is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_context(runner, case: dict, root: Path) -> tuple[str, str]:
    fixture_name = case.get("execution", {}).get("fixture")
    builder = runner.FIXTURES.get(fixture_name)
    if builder is None:
        raise ValueError(f"unsupported evaluation fixture: {fixture_name}")
    substitutions = builder(root)
    prompt = case["prompt"]
    if "url_placeholder" in substitutions:
        prompt = prompt.replace("this documentation URL", "the supplied site/index.html")
        prompt = prompt.replace("this page", "the supplied site/index.html")
    files = []
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        total += len(data)
        if total > MAX_FIXTURE_BYTES:
            raise ValueError(f"evaluation fixture exceeds {MAX_FIXTURE_BYTES} bytes")
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"evaluation fixture is not UTF-8: {relative}") from error
        files.append(f"--- {relative} ---\n{content}")
    return prompt, "\n".join(files)


def _generation_instruction(skill: str, skill_text: str, overlay: str | None) -> str:
    overlay_section = ""
    if overlay is not None:
        overlay_section = (
            "\n\nThe following project Overlay supplements the Skill and must influence the response "
            "without replacing the global Skill:\n<overlay>\n" + overlay + "\n</overlay>"
        )
    return (
        f"Act as the ${skill} Skill. Return only the final user-facing answer for the supplied "
        "case. The supplied artifacts are read-only evidence; do not claim to run tools or edit "
        "files. Follow the Skill instructions faithfully.\n\n<skill>\n"
        + skill_text + "\n</skill>" + overlay_section
    )


def _judge_instruction() -> str:
    return (
        "You are a strict, blind A/B evaluator. Evaluate Response A and Response B only against "
        "the supplied case rubric. Do not infer which response is the candidate. Return JSON only "
        "with keys A, B, preferred, newHardErrors, and obviousRegression. A and B must each contain "
        "hardRequirements (Boolean array where true means the requirement was satisfied), "
        "forbiddenBehaviorsObserved (Boolean array where true means the forbidden behavior was "
        "observed in the response), qualityScore "
        "(integer 0-100), hardErrors (array of concise strings), and notes (string). preferred must "
        "be A, B, or tie. obviousRegression must be an object with response (A, B, or none) and "
        "reason (string). A hard error is a concrete correctness, safety, authorization, or contract "
        "failure; style preferences alone are not hard errors. newHardErrors must be an array of "
        "objects with response (A or B) and description, and must contain only hard errors present "
        "in that response but absent from the other response."
    )


def _validated_judgment(value: dict, case: dict) -> dict:
    if not isinstance(value, dict) or value.get("preferred") not in {"A", "B", "tie"}:
        raise ValueError("LLM judge returned an invalid comparison")
    expected_hard = len(case["hard_requirements"])
    expected_forbidden = len(case["forbidden_behaviors"])
    for label in ("A", "B"):
        item = value.get(label)
        if not isinstance(item, dict):
            raise ValueError("LLM judge omitted a response score")
        hard = item.get("hardRequirements")
        forbidden = item.get("forbiddenBehaviorsObserved")
        score = item.get("qualityScore")
        errors = item.get("hardErrors")
        if (not isinstance(hard, list) or len(hard) != expected_hard
                or any(not isinstance(flag, bool) for flag in hard)):
            raise ValueError("LLM judge returned invalid hard requirement decisions")
        if (not isinstance(forbidden, list) or len(forbidden) != expected_forbidden
                or any(not isinstance(flag, bool) for flag in forbidden)):
            raise ValueError("LLM judge returned invalid forbidden behavior decisions")
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise ValueError("LLM judge returned an invalid quality score")
        if not isinstance(errors, list) or any(not isinstance(error, str) for error in errors):
            raise ValueError("LLM judge returned invalid hard errors")
    regression = value.get("obviousRegression")
    if (not isinstance(regression, dict)
            or regression.get("response") not in {"A", "B", "none"}
            or not isinstance(regression.get("reason"), str)):
        raise ValueError("LLM judge returned invalid regression evidence")
    new_errors = value.get("newHardErrors")
    if (not isinstance(new_errors, list) or any(
        not isinstance(item, dict) or item.get("response") not in {"A", "B"}
        or not isinstance(item.get("description"), str) or not item["description"].strip()
        for item in new_errors
    )):
        raise ValueError("LLM judge returned invalid comparative hard errors")
    return value


def _aggregate_usage(usages: list[dict]) -> dict:
    reported = [usage for usage in usages if usage.get("status") == "reported"]
    cached = [usage for usage in usages if usage.get("status") == "cached"]
    return {
        "reportedCalls": len(reported),
        "cachedCalls": len(cached),
        "unreportedCalls": len(usages) - len(reported) - len(cached),
        "inputTokens": sum(int(item.get("inputTokens", 0)) for item in reported),
        "outputTokens": sum(int(item.get("outputTokens", 0)) for item in reported),
        "totalTokens": sum(int(item.get("totalTokens", 0)) for item in reported),
        "cost": {"status": "cost_unavailable", "amount": None, "currency": None},
    }


def _baseline_cache_path(
    output_root: Path, *, skill: str, skill_digest: str, corpus_digest: str,
    baseline_overlay_content: str | None, model: str, cache_identity: str,
) -> Path:
    key = json.dumps({
        "format": EVALUATION_FORMAT,
        "gateVersion": GATE_VERSION,
        "skill": skill,
        "skillDigest": skill_digest,
        "corpusDigest": corpus_digest,
        "baselineOverlayDigest": (
            _sha256_text(baseline_overlay_content)
            if baseline_overlay_content is not None else None
        ),
        "model": model,
        "cacheIdentity": cache_identity,
    }, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return output_root / "cache" / f"baseline-{digest}.json"


def _read_baseline_cache(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict) or value.get("format") != "forge-overlay-baseline-cache-v1":
        return {}
    entries = value.get("entries")
    return entries if isinstance(entries, dict) else {}


def _write_baseline_cache(path: Path, entries: dict) -> None:
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps({
            "format": "forge-overlay-baseline-cache-v1", "entries": entries,
        }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def evaluate_overlay(
    *,
    forge_root: Path,
    skill_root: Path,
    skill: str,
    overlay_content: str,
    model: str,
    output_root: Path,
    call_llm: Callable[[str, object], tuple[str, dict]],
    baseline_overlay_content: str | None = None,
    baseline_cache_identity: str | None = None,
    force_baseline: bool = False,
) -> tuple[dict, dict]:
    """Run fixed cases and return a compact gate report plus full audit artifact."""
    corpus_path = forge_root / "evals" / "skill-behavior-cases.json"
    corpus_bytes = corpus_path.read_bytes()
    corpus = json.loads(corpus_bytes.decode("utf-8"))
    cases = _compatible_cases(corpus, skill)
    if not cases:
        raise ValueError(f"no HTTP-compatible fixed read-only evaluation cases exist for Skill: {skill}")
    if len(cases) < MIN_EVALUATION_CASES:
        raise ValueError(
            f"automatic publication requires at least {MIN_EVALUATION_CASES} compatible fixed cases "
            f"for Skill {skill}; found {len(cases)}"
        )
    skill_path = skill_root.parent / skill / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"global Skill is unavailable: {skill}")
    skill_text = skill_path.read_text(encoding="utf-8")
    skill_digest = _sha256_file(skill_path)
    corpus_digest = "sha256:" + hashlib.sha256(corpus_bytes).hexdigest()
    cache_path = None
    baseline_cache = {}
    if baseline_cache_identity:
        cache_path = _baseline_cache_path(
            output_root, skill=skill, skill_digest=skill_digest,
            corpus_digest=corpus_digest,
            baseline_overlay_content=baseline_overlay_content, model=model,
            cache_identity=baseline_cache_identity,
        )
        if not force_baseline:
            baseline_cache = _read_baseline_cache(cache_path)
    runner = _load_runner(forge_root)
    results = []
    all_usage = []
    baseline_cache_hits = 0
    baseline_cache_misses = 0
    fixture_parent = output_root / ".fixtures"
    fixture_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="forge-overlay-eval-", dir=fixture_parent) as temporary:
        temp_root = Path(temporary)
        for index, case in enumerate(cases):
            case_root = temp_root / case["id"]
            case_root.mkdir(parents=True)
            prompt, fixture = _fixture_context(runner, case, case_root)
            request = {"case": prompt, "artifacts": fixture}
            prompt_digest = _sha256_text(prompt)
            fixture_digest = _sha256_text(fixture)
            cached = baseline_cache.get(case["id"])
            if (isinstance(cached, dict) and cached.get("promptDigest") == prompt_digest
                    and cached.get("fixtureDigest") == fixture_digest
                    and isinstance(cached.get("response"), str)):
                baseline = cached["response"]
                baseline_usage = {"status": "cached"}
                baseline_cache_hits += 1
            else:
                baseline, baseline_usage = call_llm(
                    _generation_instruction(skill, skill_text, baseline_overlay_content), request
                )
                baseline_cache[case["id"]] = {
                    "promptDigest": prompt_digest, "fixtureDigest": fixture_digest,
                    "response": baseline,
                }
                baseline_cache_misses += 1
            candidate, candidate_usage = call_llm(
                _generation_instruction(skill, skill_text, overlay_content), request
            )
            # Alternate labels deterministically so the judge cannot learn a fixed candidate side.
            candidate_label = "A" if index % 2 else "B"
            responses = {candidate_label: candidate}
            responses["B" if candidate_label == "A" else "A"] = baseline
            judge_payload = {
                "caseId": case["id"],
                "prompt": prompt,
                "artifacts": fixture,
                "hardRequirements": case["hard_requirements"],
                "forbiddenBehaviors": case["forbidden_behaviors"],
                "responseA": responses["A"],
                "responseB": responses["B"],
            }
            judge_text, judge_usage = call_llm(_judge_instruction(), judge_payload)
            try:
                judgment = _validated_judgment(json.loads(judge_text), case)
            except json.JSONDecodeError as error:
                raise ValueError("LLM judge returned non-JSON output") from error
            baseline_label = "B" if candidate_label == "A" else "A"
            baseline_score = judgment[baseline_label]
            candidate_score = judgment[candidate_label]
            candidate_regressed = judgment["obviousRegression"]["response"] == candidate_label
            comparative_candidate_errors = [
                item["description"] for item in judgment["newHardErrors"]
                if item["response"] == candidate_label
            ]
            results.append({
                "caseId": case["id"],
                "category": case["category"],
                "promptDigest": prompt_digest,
                "fixtureDigest": fixture_digest,
                "candidateBlindLabel": candidate_label,
                "baseline": {**baseline_score, "responseDigest": _sha256_text(baseline)},
                "candidate": {**candidate_score, "responseDigest": _sha256_text(candidate)},
                "preferred": judgment["preferred"],
                "obviousCandidateRegression": candidate_regressed,
                "regressionReason": judgment["obviousRegression"]["reason"],
                "newCandidateHardErrors": comparative_candidate_errors,
                "responses": {"baseline": baseline, "candidate": candidate},
                "usage": {"baseline": baseline_usage, "candidate": candidate_usage, "judge": judge_usage},
            })
            all_usage.extend((baseline_usage, candidate_usage, judge_usage))

    if cache_path is not None and baseline_cache_misses:
        _write_baseline_cache(cache_path, baseline_cache)

    baseline_scores = [item["baseline"]["qualityScore"] for item in results]
    candidate_scores = [item["candidate"]["qualityScore"] for item in results]
    baseline_checks = [flag for item in results for flag in item["baseline"]["hardRequirements"]]
    candidate_checks = [flag for item in results for flag in item["candidate"]["hardRequirements"]]
    new_hard_errors = []
    for result, case in zip(results, cases):
        new_hard_errors.extend(
            f"{result['caseId']}: {error}" for error in result["newCandidateHardErrors"]
        )
        for index, (baseline_ok, candidate_ok) in enumerate(zip(
            result["baseline"]["hardRequirements"], result["candidate"]["hardRequirements"]
        )):
            if baseline_ok and not candidate_ok:
                new_hard_errors.append(f"{result['caseId']}: {case['hard_requirements'][index]}")
        for index, (baseline_seen, candidate_seen) in enumerate(zip(
            result["baseline"]["forbiddenBehaviorsObserved"],
            result["candidate"]["forbiddenBehaviorsObserved"]
        )):
            if not baseline_seen and candidate_seen:
                new_hard_errors.append(f"{result['caseId']}: {case['forbidden_behaviors'][index]}")
    new_hard_errors = sorted(set(new_hard_errors))
    baseline_average = sum(baseline_scores) / len(baseline_scores)
    candidate_average = sum(candidate_scores) / len(candidate_scores)
    baseline_pass_rate = sum(baseline_checks) / len(baseline_checks) if baseline_checks else 1.0
    candidate_pass_rate = sum(candidate_checks) / len(candidate_checks) if candidate_checks else 1.0
    obvious_regressions = [item["caseId"] for item in results if item["obviousCandidateRegression"]]
    gates = [
        {"id": "minimum_case_coverage", "passed": True,
         "detail": {"required": MIN_EVALUATION_CASES, "actual": len(results)}},
        {"id": "no_new_hard_errors", "passed": not new_hard_errors, "detail": new_hard_errors},
        {"id": "candidate_average_not_lower", "passed": candidate_average >= baseline_average,
         "detail": {"baseline": round(baseline_average, 2), "candidate": round(candidate_average, 2)}},
        {"id": "key_checkpoint_rate_not_lower", "passed": candidate_pass_rate >= baseline_pass_rate,
         "detail": {"baseline": round(baseline_pass_rate, 4), "candidate": round(candidate_pass_rate, 4)}},
        {"id": "no_obvious_single_case_regression", "passed": not obvious_regressions,
         "detail": obvious_regressions},
    ]
    passed = all(item["passed"] for item in gates)
    compact_cases = [{key: value for key, value in item.items() if key not in {"responses", "usage"}} for item in results]
    report = {
        "format": EVALUATION_FORMAT,
        "evaluator": "blind-llm-ab-judge-v1",
        "model": model,
        "baseline": "active_overlay" if baseline_overlay_content is not None else "global_skill",
        "skillDigest": skill_digest,
        "candidateOverlayDigest": _sha256_text(overlay_content),
        "corpusDigest": corpus_digest,
        "caseCount": len(results),
        "confidence": "LOW" if len(results) < 3 else "MEDIUM" if len(results) < 10 else "HIGH",
        "judgeCalibration": "uncalibrated_user_approved_gate",
        "gateVersion": GATE_VERSION,
        "passed": passed,
        "gates": gates,
        "cases": compact_cases,
        "usage": _aggregate_usage(all_usage),
        "baselineCache": {
            "enabled": cache_path is not None, "forced": force_baseline,
            "hits": baseline_cache_hits, "misses": baseline_cache_misses,
        },
    }
    artifact = {**report, "cases": results}
    return report, artifact
