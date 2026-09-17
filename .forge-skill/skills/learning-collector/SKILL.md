---
name: learning-collector
description: Experimental, opt-in collection, review, summarization, Overlay generation, evaluation, and feedback control for project-scoped Forge Skill training. Model calls, publication, and activation remain explicit operator actions.
---

# Learning Collector / Skill Training Data Collector

This is an experimental hidden capability. Do not suggest or invoke it unless
the user explicitly asks to configure, collect, inspect, or review Skill
learning/training data. It remains disabled until a project explicitly lists a
Skill in `.forge-skill/learning/config.json`.

In this capability, Skill learning and Skill training mean improving a Forge
Skill's external instructions, workflow, judgment rules, output contract, and
regression cases from reviewed evidence. They never mean training model
parameters. The implemented lifecycle ends in a project-scoped Overlay; it
does not rewrite the global Skill.

## Lifecycle

The stable flow is evidence collection -> human record review -> Summary ->
human Summary review -> Overlay -> human Overlay review -> evaluation and
publication -> manual activation -> reviewed production feedback. Summary
knowledge never runs directly, and an Overlay never replaces the global Skill.
Phases 1-8 are implemented; evaluation evidence remains provisional until the
planned Phase 9 qualification is accepted. When managing versions, evaluation,
release evidence, or rollback behavior, read
[`references/lifecycle.md`](references/lifecycle.md) for the authoritative phase
states, gates, and operator boundaries.

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

Store records in the shared Forge data root, partitioned by project and Skill:

```text
forge-data/projects/<projectId>/learning/<skill>/learning.sqlite
```

The project keeps only `.forge-skill/learning/config.json` and `project.json`.
The global `forge-data/project-registry.json` enables cross-project review;
databases remain physically isolated under their project ID.
Summary versions are training knowledge only. They are never loaded directly
at runtime; a project Overlay references one or more reviewed summaries and is
the only runtime correction layer.

On first collection, create `.forge-skill/learning/project.json` with a stable
UUID-based `projectId`. This identity moves with the project. The registry keeps
the mutable physical path.

When the same ID appears at a new path, use the old registered path to resolve
the situation:

- Old path missing: treat it as a move, preserve the ID, and update the registry.
- Old path still present: treat it as a copy, generate a new ID for the copy,
  register it separately, and migrate the copied SQLite records to the new ID.

Copied history remains available in both projects; subsequent records diverge.
Registry health states are `ACTIVE`, `UNAVAILABLE`, `CONFLICT`, and `DISABLED`.
The review service persists availability changes with `unavailableSince` and
`healthReason`, so missing or moved projects remain diagnosable between runs.
An operator may archive a project registration from the dashboard. Archiving
sets it to `DISABLED` and excludes it from unfiltered cross-project scans; it
does not delete any project configuration, records, summaries, Overlays, or
evaluation artifacts. An explicitly selected archived project remains
inspectable and can be restored. A later collection from that project may
reactivate its registration because the project's `enabledSkills` config is
the source of truth. Conflicting identities must be resolved before their
registration status can be changed.

Records are `ACTIVE` by default. Review may mark them `EXCLUDED`, edit their
effective content, add a note, or permanently delete them from the owning
SQLite database. Deletion is irreversible and removes the record from the
dashboard. Once a Summary references a record, that source record is immutable
and cannot be edited, excluded, re-approved, or deleted; create a new Summary
from corrected records instead. Collection errors must never block the
original Forge operation.

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
pending refinement. Dedicated deterministic profiles currently cover
`code-review`, `debug`, `implement`, `page-test`, `test-implementation`,
`refactor`, `explain`, `plan`, and `explore`. They extract only recognized
structured fields, explicit `learningSignals`, or human-reviewed plain-text
edits. Within these specialized extractors, a candidate derived from ordinary
Skill output needs evidence from at least two independent records unless an
explicit `learningSignal` or a human review note confirms that it is reusable.
This keeps one-off task answers, current UI descriptions, and project facts out
of their training rules. All generated rules start as `PENDING`.

The separate `/versions` page allows an operator to edit each rule, confirm or
exclude it, and permanently delete non-archived versions. A Summary is training
knowledge only: it is never enabled or loaded directly at runtime. An operator
may generate a project Overlay from one or more reviewed Summary versions; the
result requires separate review, evaluation, publication, and activation.
While an Overlay references a Summary, that Summary cannot be edited or deleted;
delete the non-active Overlay first when its source needs to be replaced.
Summary generation is deterministic by default and does not invoke a model
automatically. The `/versions` page exposes an explicit LLM refinement action
and local configuration. The API base URL, model, enabled state, wire API, request
timeout, and API-key environment-variable name are stored in
`llm-refiner.json`; the secret stays in the host environment. Refinement uses a
`DRAFT` as its immutable
source and creates a new version. It forces all returned rules to `PENDING`,
allows an empty rule set when no reusable adjustment remains, and rejects
invalid, oversized, unknown, damaged-Unicode, or concurrently changed source
output without changing the source version.
Refinement sends bounded, reviewed effective source content and review notes
to the configured LLM only after an explicit confirmation. The model first
classifies every candidate as KEEP, DISCARD, or CONFLICT; only KEEP candidates
enter a second synthesis call. The resulting draft holds at most six executable
rules with triggers, verification guidance, evidence IDs, and operator-visible
classification reasons. The model cannot choose confidence or cite rejected
candidates. Large records and evidence packets fail explicitly instead of
silently dropping sources. No refined rule is automatically confirmed or loaded.
Responses API refinement and evaluation
share the same relay-compatible request shape and do not request streaming or
send a temperature override. If a compatible relay returns an event stream
anyway, streamed text is accepted only after a valid
`response.completed` event; failed, incomplete, malformed, interrupted, or
oversized streams never create or update a Summary or evaluation artifact.
The configured base URL excludes the operation path. The server appends
`/responses` for the Responses API or `/chat/completions` for Chat Completions;
legacy full endpoints are normalized so the operation path is never duplicated.
The review and versions pages share a browser-local Chinese/English interface
preference. This preference affects labels and explicit LLM refinement output,
not the language of collected evidence. Each refinement request sends the
selected `zh-CN` or `en` language to the server, which constrains human-readable
rule titles, instructions, and rationales and records the choice in the new
Summary version metadata.

The phase table above is the authoritative Overlay lifecycle. The dashboard
must not collapse generation, review, evaluation, publication, and activation
into one transition. Model execution occurs only after the operator selects the
explicit evaluation or refinement action. Cases requiring real writes, shell,
or browser execution are not simulated through the HTTP evaluator. A missing
compatible case, fewer than three compatible cases, failed structural check,
concurrent Overlay change, or concurrent Baseline switch prevents publication.
The versions page exposes the compatible-case count and disables automatic
evaluation and publication until the three-case minimum is met.

The Forge natural-language entrypoint recognizes the localized learning-review
start and stop intents implemented by `_learning_review_intent`. Starting
reuses a verified existing instance or selects an available loopback port.
Stopping verifies the saved random token and PID before terminating the process.
The service is never installed as an operating-system service and does not
start automatically with Forge.

## Boundaries

Do not load a Summary directly into another Skill, update Memory, or modify a
global Skill. LLM evaluation and Overlay publishing are allowed only through
the explicit dashboard action; neither operation activates an Overlay.

## Direct host execution

An enabled Skill's direct-host lifecycle makes one pre-execution Overlay lookup
through `scripts/resolve_direct_overlay.py`, then one post-delivery collection
attempt through `scripts/record_direct_result.py`. The resolver is read-only;
the collector checks the same project allowlist and writes to the project Skill
database. Disabling a Skill is therefore both a collection switch and an
Overlay runtime kill switch. Applied Overlay identity is retained in collection
metadata without copying the Overlay content. Only user-visible result evidence
is collected, never hidden reasoning.

The direct-host contract is strict and best-effort:

- Read `pythonExecutable` and `directCollectionTimeoutSeconds` from
  the project installation's `forge-data/runtime.json`. Do not use the Windows `py` launcher and do
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
