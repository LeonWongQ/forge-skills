# AUTOLOAD.md

## Purpose

This file defines the global autoload policy for using this repository as a full, available module system without treating every module as active context in every task.

The repository may be fully present in the workspace, but that does **not** mean every file should be treated as active guidance at all times.

This file exists to ensure that:
- full repository availability does not become full-context overload
- task-relevant modules are activated selectively
- the system remains modular in practice, not only in structure
- Claude Code or similar environments can operate with a predictable task-scoped loading model

---

## Core Rule

**Available modules are not the same as active modules.**

The full repository may be visible and accessible.
Only a task-relevant subset should be treated as active context for the current task.

The system should operate through selective activation, not universal activation.

---

## Autoload Goal

The purpose of autoload is to:

1. recognize the task type
2. activate the smallest sufficient module set
3. expand only when task complexity requires it
4. preserve correctness, clarity, and speed
5. avoid turning the modular system back into a monolithic prompt

---

## Global Loading Policy

### Always Available
The repository structure, registry, packs, and module files may all exist in the workspace.

### Not Always Active
Do **not** assume that all of the following are active by default:
- all behaviors
- all domains
- all templates
- all checklists
- all runtime files
- all packs

Default activation must remain selective.

---

## Default Active Baseline

Unless the task clearly requires more, start from the smallest baseline:

- `CLAUDE.md`
- this file (`AUTOLOAD.md`)

Optionally treat the following as low-cost baseline references when useful:
- `runtime/router.md`
- `runtime/runtime-contract.md`

Do not automatically activate all domains, all behaviors, or all templates at startup.

---

## Ask Ownership Gate

Before Forge-internal skill and pack routing, preserve host ownership in this order:

1. Forge Runtime lifecycle intent (suspend/list/continue) uses its dedicated handling.
2. An explicit `/skill` invocation remains host-owned and is never reinterpreted by Forge.
3. Native-first specialist capabilities and Forge-first engineering skills are selected by the versioned `ask_policy` in `registry/skill-routing.json`.
4. If no Forge-first composition applies, `forge ask` returns an intentional native fallback.

`forge ask` emits a decision/handoff only. It does not execute a Claude Code skill, start an app, modify configuration, or advance a host session.

## Mandatory Routing Gate

For recognized engineering tasks, routing evaluation must happen before direct response generation.

The evaluation order is:
1. explicit skill match (forge skills in `skills/` directory, or external Claude Code skills)
2. strong or useful pack match
3. runtime routing

If both a skill and a pack match: prefer the pack when the task is technology-specific (e.g., "Spring service review"), prefer the skill when the task is general (e.g., "review this code").

If a task matches a known skill, pack, or routed behavior category, do not skip directly to free-form response.

Direct free-form response is allowed only when:
- no suitable skill/pack/route exists
- the user explicitly requests an informal lightweight answer
- or the task is too trivial to benefit from structured execution

---

## Autoload Sequence

Use this sequence to determine what becomes active.

### Step 1: Frame the task
Identify:
- what the user is asking for
- whether the task is small or substantial
- whether the task is analysis, implementation, explanation, or reporting oriented

### Step 2: Try skill match first
If the task matches a known skill in `.claude/skills/`, prefer skill-driven activation.

Skills are pre-composed, high-frequency task workflows. A skill bundles a verified combination of behavior + domains + template + checklists + workflow for a general task category.

Available skills:
- `code-review` — review local diffs, code snippets, artifacts
- `debug` — diagnose failures with hypothesis-driven analysis
- `plan` — create implementation or refactor plans
- `error-analysis` — analyze errors, stack traces, logs
- `report` — generate test, incident, review, or task reports
- `explain` — explain concepts with progressive depth
- `refactor` — plan structural improvements with behavior preservation
- `optimize` — improve performance with measurement-driven analysis
- `document` — create documentation with accuracy and audience focus
- `test-design` — design test strategies and plans
- `incident` — coordinate production-incident analysis
- `test-implementation` — implement focused test coverage
- `migration` — plan compatibility-preserving migrations
- `explore` — map an unfamiliar request before committing to a mode
- `page-test` — plan and assess browser/UI testing
- `test-strategy` — define broader verification strategy
- `implement` — carry out implementation-oriented changes
- `architecture-design` — design system or API architecture
- `security-review` — review security-sensitive code and configuration
- `data-design` — design data models and persistence boundaries
- `dependency-audit` — assess dependency health and exposure
- `release-readiness` — assess go/no-go release readiness
- `contract-compatibility` — assess API or event contract compatibility
- `auto-compact` — compact and preserve ongoing session context
- `vite-vue3` — work on evidence-confirmed Vue 3/Vite projects
- `vue2` — work on evidence-confirmed Vue 2.0–2.6 projects
- `vue2-7` — work on evidence-confirmed Vue 2.7 projects

If a skill is a match, activate that skill's composition first. The skill body in `.claude/skills/<name>/SKILL.md` defines the full module composition.

If both a skill and a pack match the same task: prefer the pack when technology-specific, prefer the skill when general. Skills and packs complement each other — skills for broad task categories, packs for specific technology scenarios.

### Step 3: Try pack match
If no skill matches, or if the task is technology-specific rather than general, try pack-driven activation.

If the task matches a known pack, or the pack would clearly improve consistency, speed, or output quality, prefer pack-driven activation.

Use a pack when:
- the task strongly matches a known pattern
- or the pack would clearly improve consistency, speed, or output quality

Examples:
- Spring service review
- Playwright flaky test diagnosis
- Redis stale-read incident analysis
- Java refactor planning
- test plan creation
- test report generation
- review routing
- general exploration / scoping

If a pack is a useful fit, activate that pack's composition first.

### Step 4: If no skill or pack fits, select primary behavior
Choose one primary behavior:
- review
- debug
- refactor
- optimize
- document
- explain

Secondary behaviors may be added only if they materially improve the answer.

### Step 5: Select only relevant domains
Activate only domains that materially affect technical judgment.

Do not activate domains:
- only because they exist somewhere in the repository
- only because they are adjacent to the current problem
- only for "coverage"

### Step 6: Select the smallest safe workflow
Prefer the smallest workflow path that preserves correctness and usability.

Use full workflows for non-trivial engineering tasks.
Use lighter workflows for compact review or explanation tasks.

### Step 7: Select template and checklists
Choose:
- one output template
- general quality checks
- behavior-specific checks when relevant
- verification checks when claim strength requires them

### Step 8: Expand only if needed
If the task grows in complexity, uncertainty, or risk:
- add domains
- deepen workflow
- switch templates if needed
- add verification rigor

Expansion should be intentional, not automatic.

---

## Pack-First Policy

When a task matches a stable pack, or the pack would clearly improve consistency, speed, or output quality, prefer pack activation over fully manual assembly.

Packs are the preferred fast path for repeated, well-understood scenarios.

Use a pack when:
- the task strongly matches a known pattern
- or the pack would clearly improve consistency, speed, or output quality

Typical pack-friendly tasks include:
- Spring review
- Playwright flaky debug
- Redis incident analysis
- Java refactor
- test plan creation
- test report generation
- review routing

If no pack is a useful fit, use runtime routing instead.

---

## Minimal-First Policy

Start small.

For many tasks, the best first active set is:

- `CLAUDE.md`
- one behavior
- one or two domains
- one template
- `checklist.general_quality`

Only deepen if the task requires it.

Examples:
- small Java correctness check -> `review + java + default`
- concept question about Spring transactions -> `explain + spring + explanation`
- flaky Playwright issue -> `debug + playwright + testing + debug-report`

Do not start every task with the full architecture stack active.

---

## Escalation Rules

Expand the active module set when:

- the task crosses multiple technical boundaries
- the initial behavior is no longer sufficient
- confidence is weakened by missing context
- verification needs become stronger
- the task shifts from analysis to implementation or report generation
- a pack fit becomes clearer after initial framing

Examples:
- add `domain.spring` if transaction/proxy behavior becomes central
- add `domain.redis` if stale-read/cache invalidation behavior is involved
- add `domain.testing` if confidence or verification quality becomes central
- switch from `template.default` to `template.review_report` if findings become substantial

---

## Active Context Priorities

When multiple modules are active, interpret them in this order:

1. `CLAUDE.md`
2. `AUTOLOAD.md`
3. runtime routing / runtime contract
4. primary behavior
5. active domains
6. workflow stages
7. template
8. checklists
9. report artifact shape if used

This order is not a replacement for formal conflict resolution, but a practical activation hierarchy.

---

## Lightweight Task Rule

For small tasks, do not over-activate.

Examples of lightweight tasks:
- short code clarification
- small Java correctness question
- quick explanation of one framework mechanism
- compact review of a single method
- quick test assertion sanity check

In such tasks:
- prefer `template.default`
- avoid activating many domains
- avoid full workflow unless risk justifies it
- keep the answer direct

---

## Heavyweight Task Rule

For substantial tasks, activate more rigor intentionally.

Examples of heavyweight tasks:
- multi-layer backend bug diagnosis
- production incident analysis
- refactor planning across modules
- test planning for a release
- test reporting with risk posture
- cache consistency review involving DB + framework + cache

In such tasks:
- prefer packs when available
- use stronger workflows
- activate multiple relevant domains
- apply verification checks
- use a specialized template

---

## Anti-Patterns

Avoid the following:

### Anti-pattern 1: full activation by default
Do not treat all modules as active merely because they are present.

### Anti-pattern 2: pack blindness
Do not rebuild common compositions manually if a useful pack already exists.

### Anti-pattern 3: domain inflation
Do not activate many domains to feel thorough.

### Anti-pattern 4: workflow inflation
Do not force full discover -> evidence -> context -> reasoning -> planning -> execution -> verification -> delivery on every trivial task.

### Anti-pattern 5: template inflation
Do not turn every short answer into a formal report.

### Anti-pattern 6: hidden escalation
If the active context expands materially, let the task handling reflect that intentionally.

---

## Relationship to Other Files

### Relationship to `CLAUDE.md`
`CLAUDE.md` defines universal operating principles.
This file defines how to activate the modular system practically.

### Relationship to `runtime/router.md`
`runtime/router.md` defines routing logic.
This file defines the global policy for when and how routing should drive activation.

### Relationship to `runtime/runtime-contract.md`
`runtime/runtime-contract.md` defines execution invariants and safeguards.
This file defines how to enter that runtime model from a full repository context.

### Relationship to packs
Packs are preferred fast paths for repeated task types.
This file explains when to prefer them.

---

## Recommended Operating Modes

### Mode 1: Minimal mode
Use for:
- quick questions
- compact analysis
- one-file review
- small explanation tasks

Typical active set:
- `CLAUDE.md`
- one behavior
- one domain
- `template.default`
- `checklist.general_quality`

### Mode 2: Structured engineering mode
Use for:
- code review
- diagnosis
- refactor planning
- optimization planning
- testing analysis

Typical active set:
- `CLAUDE.md`
- `AUTOLOAD.md`
- runtime routing
- one behavior
- multiple relevant domains
- specialized template
- relevant checklists

### Mode 3: Pack mode
Use for:
- repeated, known task types
- standardized team workflows
- operationally mature scenario entry points

Typical active set:
- pack-defined composition
- plus runtime expansion only when needed

---

## Final Operating Reminder

When the full repository is present:

- treat the repository as a module pool
- activate selectively
- prefer pack-first for useful matches
- prefer minimal-first for small tasks
- expand only when justified
- never confuse availability with activation

The repository should feel like a modular operating system, not a giant always-on prompt.
