# Integration: Claude Code

## Purpose

This document explains how to use this repository with a Claude Code style workflow.

The repository should not be treated as one giant prompt pasted every time.
Instead, it should be used as a modular context system where the runtime selects only the files relevant to the current task.

This document describes:
- recommended loading strategy
- composition approach
- practical usage patterns
- what to avoid

---

## Core Mapping

In a Claude Code style environment, this repository maps naturally to the following model:

- `CLAUDE.md` -> global operating rules
- `/engine/*` -> internal workflow guidance
- `/behaviors/*` -> task mode activation
- `/domains/*` -> technology expertise activation
- `/templates/*` -> response structure
- `/checklists/*` -> pre-delivery quality gate
- `/reports/*` -> optional artifact outputs

Claude Code should use this repository as a modular operating context, not as a static monolith.

---

## Context Bundle Handoff

When a Claude Code host needs an explicit portable snapshot rather than selective local file reads, build a Context Bundle from a Runtime Envelope:

```text
runtime-init → context-bundle → host loads captured module content
```

The bundle contains selected Markdown modules in Forge's fixed layer order, exact UTF-8 content, source paths, byte sizes, and SHA-256 digests. It is safe to pass to a host because Forge revalidates containment before reading each selected registered path. The host should load the captured text—not resolve or reread the serialized paths—and retain the original Runtime Envelope for task state, stage progress, and output validation.

A Context Bundle does not make Forge call Claude Code, manage tools, or automatically execute workflow stages. Those remain host/session responsibilities.

### Ask ownership and handoff

`forge ask` is the host-facing ownership gateway, not an execution API. Its registry-defined order is Runtime lifecycle intent, explicit `/skill` passthrough, native-first specialist handling, Forge-first composition, then intentional native fallback. The host reads the selected Forge `SKILL.md` only after a `forge_route` result; after `native_route`, explicit passthrough, or `native_fallback`, it continues native Claude Code handling. Every non-Runtime decision reports `execution: "not_executed"`.


For a caller-managed Claude Code session, create a host request after preparing the Runtime Envelope and materializing its matching Bundle:

```text
runtime-init → runtime-prepare → context-bundle → claude-code-prepare
caller-managed Claude Code session → claude-code-validate-result
→ runtime-import-result → runtime-advance → next runtime-prepare
… → final runtime-advance → validate-runtime-output
```

`claude-code-prepare` validates the Runtime Envelope/Bundle digest linkage and emits a portable JSON request. Its prompt has five ordered sections:

1. host boundary and responsibility statement;
2. stable Bundle module content in captured order;
3. dynamic Runtime Envelope task state;
4. selected engine stage and output contract;
5. normalized-result request.

The host must use captured Bundle content, not serialized paths. It owns Claude Code invocation, session IDs, workspace choice, tool permissions and execution, user approvals, streaming, retries, and result production. Forge does not invoke an SDK or CLI, discover credentials, execute tools, persist a Claude Code session, or automatically progress workflow stages.

Claude Code native background agents and `claude --resume` remain host/session features. Forge Runtime is separate: an explicitly requested `runtime-suspend` stores a caller-owned task Envelope only in the current project's `.forge-runtime/`. `forge ask` can list those envelopes through Runtime-scoped Chinese queries, and its conversational suspension request is confirmation-gated before it writes state; it neither suspends a Claude Code background agent nor resumes a Claude Code conversation. When a user asks to continue such work, the host reads that one project directory, asks the user to select a valid candidate, then consumes it once before using its Envelope in the current session. Forge does not install a SessionStart Hook or resume Claude Code conversations.

A completed host result must preserve the request/runtime/stage/Bundle digests plus the generic stage index and attempt. Run `claude-code-validate-result` before generic `runtime-import-result`. Forge then accepts `runtime-advance --action next` only for a successful current-stage result; failed or blocked results may be explicitly marked for host-owned retry or abort. No result advances automatically, and `validate-runtime-output` is available only after every selected stage has been explicitly advanced.

---


### Always load
For most sessions, always include:

- `CLAUDE.md`
- `/runtime/router.md`

These establish:
- principles
- composition rules
- baseline task routing

### Usually load
Then load:

- one primary behavior file
- one to three relevant domain files
- one template
- one or more checklists

### Sometimes load
Load additional engine files explicitly when:
- the task is complex
- the task spans diagnosis and execution
- verification rigor matters
- the user needs a reusable report artifact

Possible additions:
- `runtime/runtime-contract.md`
- `runtime/conflict-resolution.md`
- specific engine stage files
- `reports/*`

---

## Recommended Runtime Pattern

A strong Claude Code runtime loop for this repository is:

1. classify the task
2. select active modules
3. form a working plan internally
4. execute using engine stages
5. run checklist-style validation
6. deliver in the selected template

A simple internal control flow might look like:

```text
load CLAUDE.md
load runtime/router.md
detect behavior
detect domains
select template
run discover/evidence/context/reasoning/...
apply checklists
deliver
```

---

## Suggested Session Workflow

### Step 1: identify task mode

Examples:

- code review -> `behaviors/review.md`
- bug diagnosis -> `behaviors/debug.md`
- refactor -> `behaviors/refactor.md`
- concept explanation -> `behaviors/explain.md`

### Step 2: identify domain set

Examples:

- Java + Spring service -> `domains/java.md`, `domains/spring.md`
- Redis consistency issue -> `domains/redis.md`, maybe `domains/mysql.md`
- flaky browser test -> `domains/playwright.md`, `domains/testing.md`

### Step 3: choose workflow depth

Use:
- light path for explanation or compact review
- full path for risky code work or diagnosis

### Step 4: choose output shape

Examples:

- review -> `templates/review-report.md`
- debug -> `templates/debug-report.md`
- short response -> `templates/default.md`

### Step 5: quality gate

Before final output, mentally apply:

- `checklists/general-quality.md`
- task-specific checklist
- `delivery-checklist.md`
- `verification-checklist.md` when correctness matters

---

## Good Claude Code Usage Patterns

### Pattern 1: modular preloading
Keep a small stable base:
- `CLAUDE.md`
- `runtime/router.md`

Then selectively add:
- behavior
- domains
- template
- checklists

This keeps context efficient.

### Pattern 2: task-relevant narrowing
Do not load every domain.
Load only what materially affects the current task.

### Pattern 3: report emission when needed
If the task needs a reusable artifact, use:
- `reports/task-report.md`
- `reports/incident-report.md`
- `reports/review-summary.md`

### Pattern 4: progressive depth
Start with a compact task composition.
Only add more modules if the task becomes deeper or more ambiguous.

---

## Example Compositions

### Example: Spring Redis review

Load:
- `CLAUDE.md`
- `runtime/router.md`
- `behaviors/review.md`
- `domains/java.md`
- `domains/spring.md`
- `domains/redis.md`
- `domains/testing.md`
- `templates/review-report.md`
- `checklists/general-quality.md`
- `checklists/review-checklist.md`
- `checklists/verification-checklist.md`
- `checklists/delivery-checklist.md`

### Example: Playwright flaky test

Load:
- `CLAUDE.md`
- `runtime/router.md`
- `behaviors/debug.md`
- `domains/playwright.md`
- `domains/testing.md`
- `templates/debug-report.md`
- `checklists/general-quality.md`
- `checklists/debug-checklist.md`
- `checklists/delivery-checklist.md`

### Example: Spring transaction explanation

Load:
- `CLAUDE.md`
- `runtime/router.md`
- `behaviors/explain.md`
- `domains/spring.md`
- `domains/java.md`
- `templates/explanation.md`
- `checklists/general-quality.md`
- `checklists/delivery-checklist.md`

---

## Practical Advice for Claude Code

### Prefer composition over giant context
Do not concatenate the entire repository unless the environment absolutely requires it.

### Keep the kernel stable
`CLAUDE.md` should remain the anchor.

### Let behavior drive emphasis
If `debug` is active, do not answer like a review.
If `review` is active, do not drift into broad implementation planning unless asked.

### Let templates shape delivery
Do not make every answer a giant report.

### Use reports selectively
Reports are useful when:
- work will be handed off
- the outcome should be persisted
- incident or review history matters

---

## Anti-Patterns

Avoid:
- always loading all files
- using review mode for every engineering task
- treating domain files as workflow definitions
- treating templates as reasoning engines
- skipping checklists on high-risk tasks
- loading so much context that the active task signal gets diluted

---

## Suggested Minimal Base Pack

If you want a practical reusable Claude Code base pack, start with:

- `CLAUDE.md`
- `runtime/router.md`
- `runtime/runtime-contract.md`
- `runtime/conflict-resolution.md`
- `checklists/general-quality.md`
- `checklists/delivery-checklist.md`

Then task-load:
- one behavior
- relevant domains
- one template
- optional task checklist

This gives a strong default without overload.

---

## Short Reminder

For Claude Code, use this repo as:
- stable kernel
- selective modular context
- task-driven composition
- checklist-gated delivery
