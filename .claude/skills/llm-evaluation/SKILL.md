---
name: llm-evaluation
description: Design, implement, run, or review LLM evaluations and regression gates. Use for prompt, model, RAG, tool-calling, agent, or structured-output changes; benchmark design; quality comparisons; judge-model evaluation; acceptance thresholds; and LLM quality, latency, or cost monitoring.
---

# LLM Evaluation

Turn an LLM change into evidence, not an impression. Preserve the existing production behavior unless the user explicitly requests a behavior change.

## Workflow

1. Define the decision: name the candidate, baseline, target users, failure cost, and the exact release decision the evaluation will support.
2. Inspect existing traces, prompts, tool contracts, RAG corpus, and tests before inventing a dataset or a metric.
3. Build a versioned evaluation set. Include representative, boundary, adversarial, and known-failure cases. Remove secrets and unnecessary personal data.
4. Select task-specific metrics. Combine deterministic checks (schema validity, citations, tool arguments, policy rules) with calibrated human or judge-model scoring for subjective quality.
5. Run the baseline and candidate on the same fixed inputs and record model, prompt, retrieval, tool, temperature, timeout, and evaluator versions.
6. Compare aggregate and segmented results. Inspect regressions individually instead of relying only on an average score.
7. Define a gate: hard failures must not increase; quality must meet the stated threshold; latency and cost must remain within budget. State the confidence limits when sample sizes are small.
8. For a release, add production observability: trace ID, version identifiers, latency, token/cost estimates, failure category, sampled feedback, and a rollback condition.

For Codex-backed runs, persist only token usage explicitly reported by the backend in each case and in the aggregate run artifact. When Relay pricing is unavailable, record `cost_unavailable` with a null amount; never derive a cost from token counts or an undocumented rate. Evaluation fixtures must live below the output directory's `.fixtures` folder so prompts and logs do not expose personal system-temp paths.

## Quality Rules

- Freeze a baseline before changing prompts, models, retrieval, or tool schemas.
- Do not use an LLM judge as the only oracle for safety-critical, factual, schema, or authorization outcomes.
- Keep evaluator prompts and rubrics versioned. Check judge agreement against a small human-labeled calibration set before treating its score as a release signal.
- Require the user to assess and approve any LLM-judge rubric, thresholds, and decision meaning before the judge is used as an authoritative project or release score. Without that approval, keep judge output advisory.
- Do not require a product-specific credential variable. Discover an existing user-approved evaluator backend and credential source; if none is available, report the environment gate and do not fabricate a run.
- Never treat a benchmark increase as proof of production value when the test set overlaps training, prompt examples, or manual tuning inputs.
- Separate quality, safety, latency, and cost metrics. Do not compensate a hard safety or contract regression with a higher style score.
- Report failed cases with the input identifier and failure category; avoid exposing raw sensitive inputs in broad reports.

## Deliverables

Produce the smallest useful set: evaluation objective, dataset manifest, metric/rubric definitions, baseline-versus-candidate comparison, regression list, gate decision, and production monitoring plan. Implement automation only after the assertions and acceptance criteria are explicit.
