# Runtime

## Purpose

This directory defines how the modular assistant system is assembled and operated at runtime.

The runtime layer is responsible for:
- task routing
- module composition
- execution contract
- conflict handling between layers

It is distinct from the workflow engine.

### Difference between `/engine` and `/runtime`

- `/engine` defines workflow stages
- `/runtime` defines how those stages are selected, assembled, and governed during execution

In other words:

- `engine` = stage logic
- `runtime` = orchestration logic

This separation keeps the architecture clear and prevents the workflow layer from becoming a dumping ground for routing and policy concerns.

---

## Files in This Directory

### `router.md`
Defines how a task is routed into a module composition.

It answers:
- what the primary behavior is
- which domains should be active
- which workflow path should be used
- which template and checklists should be applied

### `runtime-contract.md`
Defines the runtime execution contract.

It answers:
- what internal runtime state should exist
- what invariants must hold
- what simplifications are allowed
- what safeguards must not be skipped

### `conflict-resolution.md`
Defines how to resolve conflicts between:
- user requests
- safety and correctness requirements
- kernel principles
- workflow requirements
- behavior priorities
- domain heuristics
- template expectations

---

## Runtime Boot Sequence

A typical runtime should operate in this order:

1. load the kernel
2. route the task
3. instantiate runtime state
4. select workflow path
5. execute workflow stages
6. apply quality gates
7. deliver the result
8. optionally emit a report artifact

In repository terms, that usually means:

1. `CLAUDE.md`
2. `runtime/router.md`
3. selected behavior file(s)
4. selected domain file(s)
5. selected engine stages
6. selected template
7. selected checklist(s)
8. optional report artifact

---

## Minimal Runtime Flow

For most tasks, the runtime can be thought of as this pipeline:

```text
Kernel
  -> Router
  -> Runtime State
  -> Engine Path
  -> Template
  -> Checklists
  -> Delivery
```

This is the minimum useful mental model for operating the repository.

---

## Runtime State Model

A healthy runtime should maintain internal state equivalent to:

- task statement
- user goal
- primary behavior
- secondary behaviors
- active domains
- selected workflow path
- selected template
- selected checklists
- scope
- constraints
- assumptions
- evidence
- findings / hypotheses
- plan
- verification status
- open questions
- final confidence posture

This state does not need to be shown directly, but it should remain coherent internally.

---

## Runtime Interfaces

### 4. Thin Runtime Envelope Interface

The `runtime-init` command provides an additive, provider-neutral implementation of the handoff after composition resolution. It consumes a successful resolved-context manifest (or creates one using the same route/compose inputs), then emits a caller-owned JSON envelope containing:

- the embedded resolved manifest and stable digest;
- runtime state aligned with `runtime-state.schema.json`;
- evidence-backed active-domain refinement;
- an append-only lifecycle ledger;
- a prepared external-adapter request, imported-result slot, and ordered stage-progress cursor;
- explicit `runtime-advance` handoffs (`next`, `retry`, or `abort`);
- state-linked structured output-validation status.

`runtime-prepare` creates the request for the sole current stage. `runtime-import-result` records a normalized result only when it matches the active request. `runtime-advance` explicitly validates ordered `next`, host-owned `retry`, or terminal `abort`; it never invokes or controls a provider. `validate-runtime-output` is permitted only after the final stage reaches `ready_for_validation`, and validates the linked final structured output. None of these commands invokes a model, discovers credentials, scans a repository, or changes deployment behavior.

Runtime documents are written only to explicit caller-provided `--output` paths; Forge creates no automatic state directory or database. The `runtime-suspend` command is the project-local exception for an explicitly requested cross-session Forge task: it writes one caller-owned Envelope under the shared `forge-data/projects/<projectId>/runtime/paused/` store and exposes it through the project's `.forge-runtime` facade. Legacy project-local files are migrated on first access. Ordinary Claude Code background agents are not Runtime Envelopes.

`forge ask` also recognizes a small, Runtime-scoped Chinese lifecycle grammar. Querying is read-only, for example `查看挂起的 Forge Runtime 任务`, `有哪些暂停的 Forge Runtime 任务`, or `列出 Forge Runtime 挂起任务`. A natural-language suspension request must name a quoted task and is confirmation-gated: `暂停 Forge Runtime 任务“整理接口文档”` reports the exact follow-up command but writes nothing; `确认挂起 Forge Runtime 任务“整理接口文档”` persists the Envelope. The explicit command `runtime-suspend --task 整理接口文档` remains an immediate persistence request. Generic task phrases without the `Forge Runtime` scope, or without a quoted task in the conversational form, do not create Runtime state.

To continue an explicitly suspended project task, the host reads that project facade with `runtime-list-paused --directory .forge-runtime`, obtains the user's selection, then calls `runtime-consume-paused` for that selected filename. Consumption is a one-time handoff: the selected file is atomically claimed, returned to the host, and removed after a successful handoff so it cannot be resumed twice.

### 5. Context Bundle Interface

`context-bundle --runtime runtime.json` is an explicit read-only handoff for hosts that need materialized instructions. It revalidates the embedded manifest, safely resolves only selected registered module paths, and returns complete strict UTF-8 Markdown content in a fixed layer order with byte counts and SHA-256 digests. The bundle links to the runtime ID and resolved-context digest, while keeping task state and stage progress in the original Runtime Envelope.

The default limits are 256 KiB per module and 2 MiB aggregate content; materialization fails rather than silently truncating or substituting modules. Hosts should consume the captured snapshot, not reread paths. Bundle generation is not model invocation, repository scanning, automatic checklist enforcement, or a multi-stage executor.

### 6. Claude Code Host Adapter Interface

`claude-code-prepare --runtime prepared-runtime.json --bundle context-bundle.json` creates an optional, SDK-free artifact for a caller-managed Claude Code session. It validates the Bundle/Envelope digest linkage and emits ordered stable instruction content alongside dynamic runtime state, selected stage, output contract, and a result skeleton.

`claude-code-validate-result` verifies that a completed host result still links to the exact request, runtime, stage, and Bundle digest, then emits a generic adapter-result-compatible document for `runtime-import-result`. Neither command invokes Claude Code, selects a workspace, manages credentials or tools, asks for permission, runs a stage, or changes the Runtime Envelope. The external host retains those responsibilities.


The runtime layer can be understood as exposing three conceptual interfaces.

### 1. Routing Interface

Input:
- user request
- available repo/task signals

Output:
- module composition decision

Implemented by:
- `router.md`

### 2. Execution Contract Interface

Input:
- selected composition

Output:
- runtime state model
- invariants
- simplification rules
- safeguards

Implemented by:
- `runtime-contract.md`

### 3. Conflict Handling Interface

Input:
- competing instructions or pressures

Output:
- consistent resolution order
- explicit tradeoff handling

Implemented by:
- `conflict-resolution.md`

---

## Recommended Reading Order

If you are new to the runtime layer, read in this order:

1. `runtime/README.md`
2. `runtime/router.md`
3. `runtime/runtime-contract.md`
4. `runtime/conflict-resolution.md`

This gives:
- what runtime is
- how routing works
- what state and safeguards exist
- how conflicts are resolved

---

## Runtime Principles

The runtime layer should optimize for:

- minimum sufficient composition
- explicit task framing
- controlled scope
- evidence-aware execution
- honest verification
- useful delivery

It should avoid:

- loading every module by default
- hidden routing logic
- task-mode drift
- over-formalizing trivial tasks
- under-structuring risky tasks

---

## Relationship to Other Layers

### Relationship to `CLAUDE.md`
The kernel defines principles.
The runtime applies them operationally.

### Relationship to `/engine`
The runtime selects and governs engine stage usage.
It does not replace stage logic.

### Relationship to `/behaviors`
The runtime activates the relevant behavior mode(s).

### Relationship to `/domains`
The runtime activates the relevant expertise modules.

### Relationship to `/templates`
The runtime selects the output shape.

### Relationship to `/checklists`
The runtime applies quality gates before final delivery.

---

## Common Runtime Anti-Patterns

Avoid:

- putting routing rules into `/engine`
- putting workflow stage logic into `/runtime`
- activating too many domains
- allowing multiple primary behaviors
- skipping discovery on ambiguous tasks
- claiming correctness without verification
- forcing heavy templates for tiny tasks

---

## Short Reminder

Runtime is the orchestration layer.

It decides:
- what to load
- how to assemble it
- how to keep execution coherent
- how to deliver responsibly
