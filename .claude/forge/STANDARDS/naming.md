# Standard: Naming

## Purpose

This document defines naming rules for modules in this repository.

Good naming should make it easy to infer:
- the layer
- the responsibility
- the likely use case
- the difference from nearby modules

Names should reduce ambiguity, not create it.

---

## General Naming Rules

### 1. Prefer short, descriptive names
Examples:
- `review.md`
- `reasoning.md`
- `verification.md`
- `spring-ai.md`

### 2. Prefer noun-like or stage-like names by layer
- engine files: stage/action names
- behavior files: task mode names
- domain files: technology names
- template files: deliverable names
- checklist files: quality gate names
- report files: artifact names

### 3. Avoid overly clever names
Names should be obvious.

Bad:
- `deep-think.md`
- `quality-brain.md`

Better:
- `reasoning.md`
- `review-checklist.md`

### 4. Avoid overlapping names unless distinction is very clear
Do not create names that are easy to confuse.

Bad pair:
- `analysis.md`
- `reasoning.md`

unless there is a strong architectural reason.

---

## Layer-Specific Naming Rules

### Engine
Use:
- process stage names
- transition/support names if clearly operational

Good examples:
- `discover.md`
- `evidence.md`
- `planning.md`
- `transitions.md`

Avoid:
- vague abstract names
- domain names
- behavior names

### Behaviors
Use:
- working mode names

Good examples:
- `review.md`
- `debug.md`
- `refactor.md`

Avoid:
- technology names
- report names
- process stage names

### Domains
Use:
- technology or technical area names

Good examples:
- `java.md`
- `spring.md`
- `mysql.md`
- `testing.md`

Avoid:
- behavior-like names
- company/project-specific names unless this repository is intentionally project-bound

### Templates
Use:
- output artifact names

Good examples:
- `review-report.md`
- `debug-report.md`
- `implementation-plan.md`

Avoid:
- names that merely repeat behavior names unless structure is actually tied to that output

### Checklists
Use:
- `<purpose>-checklist.md`

Good examples:
- `review-checklist.md`
- `delivery-checklist.md`

Prefer consistency over variation.

### Reports
Use:
- `<artifact>.md`

Good examples:
- `incident-report.md`
- `review-summary.md`

---

## Registry ID vs Filename Convention

Registry IDs and filenames follow different conventions by design.

### Registry ID format
`<layer>.<short_name>`

Examples:
- `checklist.review`
- `checklist.delivery`
- `report.task`
- `report.incident`

IDs are optimized for machine consumption: unique, short, predictable, easy to parse.

### Filename format
`<descriptive-purpose>.md`

Examples:
- `review-checklist.md`
- `delivery-checklist.md`
- `task-report.md`
- `incident-report.md`

Filenames are optimized for human readability: they include enough context to be understood without knowing the parent directory.

### Why they differ
Registry IDs strip the layer-context suffix (e.g., `-checklist`, `-report`) because the ID prefix already encodes the layer:

- `checklist.review` — the `checklist.` prefix already tells you it's a checklist
- `report.task` — the `report.` prefix already tells you it's a report

Filenames keep the suffix because a flat file listing doesn't carry directory context.

### When this convention applies
This pattern applies primarily to:
- `/checklists` — filenames use `-checklist` suffix, ids use `checklist.*` prefix
- `/reports` — filenames use `-report` suffix, ids use `report.*` prefix

Other layers (engine, runtime, behaviors, domains, templates) typically have filenames that match the id suffix directly, because they don't carry a layer-indicating suffix.

### Rule
When the directory name already signals the layer, the filename may include a layer-reinforcing suffix for human readability. The registry ID should avoid that redundancy.

---

## Naming New Modules

Before adding a new name, ask:

- Is this name clearly tied to its layer?
- Is the responsibility obvious?
- Is it too broad?
- Is it too narrow?
- Could it be confused with an existing module?
- Does it follow existing repository patterns?

---

## Renaming Guidance

Rename a module when:
- the current name is misleading
- overlap repeatedly confuses contributors
- the module evolved into a different responsibility

If renaming:
- update references
- update architecture docs if needed
- update examples that mention the old name

---

## Short Reminder

Good names are:
- clear
- layer-appropriate
- distinct
- stable
- easy to compose mentally
