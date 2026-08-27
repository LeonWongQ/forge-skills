---
name: learning-collector
description: Collect configured Forge Skill runtime results into project-local SQLite databases and provide a local cross-project review dashboard. This skill supports the data stage of Skill learning/training; it never automatically learns, summarizes, evaluates, or modifies other Skills.
---

# Learning Collector / Skill Training Data Collector

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

Records are `ACTIVE` by default. Review may mark them `EXCLUDED` or `DELETED`,
edit their effective content, add a note, or restore them. Collection errors
must never block the original Forge runtime operation.

## Review

Run `scripts/review_server.py` to open a loopback-only dashboard. It reads all
registered project databases and applies review changes transactionally to the
owning project database.

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

Do not infer learning/training rules, summarize records, run evaluations, update
Memory, modify another Skill, or publish anything. Those capabilities require
separate approval and are intentionally outside this version.

## Direct host execution

Forge Runtime collection remains the deterministic path. When Codex or another
host loads a Forge Skill directly, the shared Forge delivery hook uses
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
