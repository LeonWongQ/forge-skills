---
name: learning-collector
description: Experimental, explicitly invoked collection and review of configured Forge Skill final results. It stores project-local evidence for optional Skill learning/training and never learns, summarizes, evaluates, or modifies Skills automatically.
---

# Learning Collector / Skill Training Data Collector

This is an experimental hidden capability. Do not suggest or invoke it unless
the user explicitly asks to configure, collect, inspect, or review Skill
learning/training data. It remains disabled until a project explicitly lists a
Skill in `.forge-skill/learning/config.json`.

这里的“学习”和“训练”指训练 Forge Skill 的外部行为：通过采集结果、人工审核和后续规则整理，改进 Skill 的提示、流程、判断规则和回归测试。它不指训练模型参数。
当前版本只实现 Skill 训练闭环的“采集 + 审核”阶段，尚未自动生成或发布 Skill 修改。

Collect independent final results from explicitly enabled Skills. The collector
itself is always excluded. One toolchain run may collect several records when it
invokes several enabled Skills, but each `project + run + Skill` combination is
stored at most once. Intermediate Runtime stages are skipped. Empty objects,
arrays, blank strings, recursively empty structures, and payloads containing
only transport status or empty diagnostics/metadata are not records and must not
create a database row.

Store one complete user-visible final result, not the full execution context.
Keep its overall conclusion, independent findings or decisions, evidence
references, verification status, and the minimum scope identifier needed to
interpret the evidence. Exclude prompts, hidden reasoning, intermediate stage
results, full context bundles, credentials, and copied project file contents.

## Configuration

Prefer the current project's `.forge-skill/learning/config.json`. Fall back to
this Skill's `config.json`; its default allowlist is empty. Configuration only
needs `enabledSkills`, for example:

```json
{"schemaVersion":"1.0","enabledSkills":["code-review"]}
```

## Storage

Store records in the current project's:

```text
.forge-skill/learning/learning.sqlite
```

Register its location in `project-registry.json` beside this file. Project
databases provide physical isolation; the registry enables cross-project review.

On first collection, create `.forge-skill/learning/project.json` with a stable
UUID-based `projectId`. This identity moves with the project. The registry keeps
the mutable physical path.

When the same ID appears at a new path, use the old registered path to resolve
the situation:

- Old path missing: treat it as a move, preserve the ID, and update the registry.
- Old path still present: treat it as a copy, generate a new ID for the copy,
  register it separately, and migrate the copied SQLite records to the new ID.

Copied history remains available in both projects; subsequent records diverge.
Registry health states are `ACTIVE`, `UNAVAILABLE`, and `DISABLED`.

Records are `ACTIVE` by default. Review may mark them `EXCLUDED`, edit their
effective content, add a note, or permanently delete them from the owning
SQLite database. Deletion is irreversible and removes the record from the
dashboard. Collection errors must never block the original Forge runtime
operation.

## Review

Run `scripts/review_server.py` to open a loopback-only dashboard. It reads all
registered project databases and applies review changes transactionally to the
owning project database.

The dashboard can generate a versioned training summary for one selected
project and Skill. A summary includes only records that are both `ACTIVE` and
reviewed, normally from the last six months plus records marked as classic
cases. The common layer controls this time window, classic-case retention,
size limits, and source traceability. Each Skill may provide a specialized
extractor; Skills without one use a generic evidence candidate and remain
pending refinement. All generated rules start as `PENDING`.

The separate `/versions` page allows an operator to edit each rule, confirm or
exclude it, enable one fully reviewed version per project and Skill, and
permanently delete non-applied versions. Legacy summaries remain readable but
cannot be newly enabled. Summary generation is deterministic by default and
does not invoke a model automatically. The `/versions` page now exposes an
explicit `LLM 精炼` action and local configuration. Only endpoint, model, and
API-key environment-variable name are stored in `llm-refiner.json`; the secret
stays in the host environment. Refinement runs only for a `DRAFT`, forces all
returned rules back to `PENDING`, and rejects invalid, oversized, or unknown
source output without changing the previous snapshot.

The Forge natural-language entrypoint manages the temporary service:

```text
forge ask "启动学习审核页面"
forge ask "关闭学习审核服务"
```

Starting reuses a verified existing instance or selects an available loopback
port. Stopping verifies the saved random token and PID before terminating the
process. The service is never installed as an operating-system service and does
not start automatically with Forge.

## Boundaries

Do not load a summary into another Skill, run evaluations, update Memory,
modify another Skill, or publish anything. Those capabilities require separate
approval and are intentionally outside this version.

## Direct host execution

Collection is triggered only by an enabled Skill's direct-host delivery
protocol. The shared Forge delivery instruction uses
`scripts/record_direct_result.py`. The script reads a JSON object from stdin,
checks the project allowlist through the same collector, and writes to the same
project SQLite database. It records only user-visible result evidence, never
hidden reasoning.

The direct-host contract is strict and best-effort:

- Read `pythonExecutable` and `directCollectionTimeoutSeconds` from
  `runtime.json` beside this file. Do not use the Windows `py` launcher and do
  not switch interpreters after a failure. A missing configured executable is
  a collection failure, not permission to discover another runtime.
- Write UTF-8 JSON bytes directly to stdin. A PowerShell native text pipeline
  is not a supported transport.
- Attempt collection once with a two-second host-side timeout. A failure may
  retain only its error type, interpreter path, and exit code; it must not delay
  delivery or trigger content conversion or another attempt.
- Invalid UTF-8 and lone Unicode surrogate code units are rejected explicitly.
  Valid Chinese, emoji, and supplementary-plane characters are preserved.

There is no Runtime, dispatcher, host after-response, background listener, or
automatic database collection trigger. Do not add a second trigger: duplicate
collection paths make invocation ownership and record counts ambiguous.
