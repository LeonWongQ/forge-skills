# Integration: Cursor

## Automated Setup

Forge provides a Cursor bootstrap rule through the supported link workflow. Run `install-link-forge.bat <target_project_path> --tool cursor`; it deploys Forge to `.cursor/forge/`, skills to `.cursor/skills/`, and rules to `.cursor/rules/`.

Cursor loads:

```
.cursor/rules/000-forge.mdc    # alwaysApply: true -- loaded into every Cursor session
```

This single file acts as forge's bootstrap in Cursor:
- **Core principles** -- condensed from the forge kernel
- **Module map** -- where to find skills, behaviors, domains, templates, checklists
- **Task routing table** -- Chinese/English trigger phrases -> correct skill + pack
- **Activation discipline** -- minimal-first, on-demand, never load all modules at once
- **Anti-patterns** -- avoid loading everything, skipping checklists, mode drift

Cursor uses the linked `.cursor/skills/` and `.cursor/forge/` directories. The link workflow does not deploy a separate `agents/` directory.

### How It Works

1. Run `install-link-forge.bat <target_project_path> --tool cursor` from the Forge source repository
2. Cursor loads `.cursor/rules/000-forge.mdc` into every session (alwaysApply: true)
3. When you type "帮我 review 这个 service", the routing table tells Cursor to read `.cursor/skills/code-review/SKILL.md`
4. The SKILL.md instructs Cursor to activate `behaviors/review.md` + `domains/spring.md` + `templates/review-report.md` + quality checklists
5. Only the task-relevant modules are loaded -- not the entire forge repository

### For New Projects

```bat
REM From the Forge source repository:
install-link-forge.bat <target_project_path> --tool cursor
```

The installer requires Python 3.11+ before it creates any project paths, then verifies deployment topology automatically before reporting success. No Forge installation, development dependencies, global `forge` command, or manual PATH change is required.

Keep the linked bootstrap spot check as an additional content-presence check:

```bash
ls .cursor/rules/000-forge.mdc
```

---

## Purpose

This document explains how to use this repository with a Cursor-style workflow.

Cursor commonly operates in a context where:
- codebase awareness is available
- prompt instructions may be attached to workspace context
- users may alternate between chat, edit, and agent-like tasks
- instructions may need to stay concise and composable

This repository works well in Cursor when treated as a modular instruction library rather than a single master prompt.

---

## Core Mapping

In a Cursor-style environment, the repository maps well to:

- workspace-level rule anchor -> `CLAUDE.md`
- task-routing layer -> `/runtime/router.md`
- mode-specific overlays -> `/behaviors/*`
- tech overlays -> `/domains/*`
- output shaping overlays -> `/templates/*`
- quality overlays -> `/checklists/*`

In practice, Cursor benefits from a layered strategy:
- stable workspace base rules
- task-specific overlays during a given interaction
- lightweight output shaping when user intent is direct

---

## Recommended Cursor Setup

### Workspace base context
Use the following as the stable base guidance for the workspace:

- `CLAUDE.md`
- `ARCHITECTURE.md` (optional for maintainers)
- `runtime/router.md`

This gives:
- universal behavior principles
- routing discipline
- separation-of-concerns awareness

### Task overlays
Per task, add:
- one behavior file
- relevant domain files
- one template if output shape matters
- one or more checklists for quality-sensitive tasks

---

## Practical Cursor Usage Modes

### Mode 1: Chat-first analysis
Good for:
- explanation
- review
- diagnosis
- planning

Recommended composition:
- kernel
- composition
- behavior
- domains
- template
- checklists

### Mode 2: Edit/refactor workflow
Good for:
- applying code transformations
- bug fix proposals
- structural cleanup

Recommended additions:
- planning
- execution
- verification
- refactor or debug behavior
- relevant domains
- verification checklist

### Mode 3: Repo-aware review
Good for:
- reviewing a PR or module in code context
- tracing framework behavior across files
- identifying hidden write or invocation paths

Recommended additions:
- evidence
- context
- reasoning
- review behavior
- domain files tied to stack
- review template

---

## Recommended Prompt Assembly Pattern

A Cursor prompt/runtime setup can internally follow this pattern:

```text
Base rules:
- CLAUDE.md
- runtime/router.md

Task overlays:
- behaviors/<mode>.md
- domains/<relevant>.md
- templates/<shape>.md
- checklists/<quality>.md
```

This avoids bloated always-on instruction sets.

---

## Suggested User-Facing Workflow

### Step 1: determine intent

Examples:
- "review this service" -> review
- "why is this failing?" -> debug
- "refactor this file" -> refactor
- "explain this annotation behavior" -> explain

### Step 2: determine stack

Examples:
- Spring service -> java + spring
- Redis cache logic -> redis (+ spring/java)
- MySQL query issue -> mysql
- Playwright test -> playwright + testing

### Step 3: determine output style

Examples:
- short answer -> default
- structured diagnosis -> debug-report
- review findings -> review-report
- refactor sequencing -> refactor-plan

### Step 4: determine whether edit is needed

If yes, use:
- planning
- execution
- verification

If no, reasoning + delivery may be enough.

---

## Cursor-Specific Advice

### Keep the stable rules small
Cursor works better when the always-on instruction layer is compact and clear.

Good stable base:
- `CLAUDE.md`
- `runtime/router.md`

Maybe add:
- `runtime/conflict-resolution.md`

Do not keep every behavior/domain permanently attached.

### Use repo awareness to reduce assumption
Since Cursor often has codebase context, prefer:
- direct evidence from files
- real imports/config/layout
- over generic framework assumptions

### Use behavior overlays to prevent mode drift
Without explicit behavior overlays, Cursor-style workflows often default into vague review/explanation blends.
Selecting `review.md`, `debug.md`, or `refactor.md` sharply improves output style.

### Use templates only when structure matters
For small interactive tasks, `default.md` is often enough.
For substantial tasks, attach the right template.

---

## Example Cursor Configurations

### Example: interactive Spring review

Base:
- `CLAUDE.md`
- `runtime/router.md`

Task overlays:
- `behaviors/review.md`
- `domains/java.md`
- `domains/spring.md`
- `domains/testing.md`
- `templates/review-report.md`
- `checklists/general-quality.md`
- `checklists/review-checklist.md`
- `checklists/delivery-checklist.md`

### Example: local refactor session

Base:
- `CLAUDE.md`
- `runtime/router.md`

Task overlays:
- `behaviors/refactor.md`
- `domains/java.md`
- `domains/spring.md`
- `domains/testing.md`
- `engine/planning.md`
- `engine/execution.md`
- `engine/verification.md`
- `templates/refactor-plan.md`
- `checklists/refactor-checklist.md`
- `checklists/verification-checklist.md`

### Example: debugging a flaky test

Base:
- `CLAUDE.md`
- `runtime/router.md`

Task overlays:
- `behaviors/debug.md`
- `domains/playwright.md`
- `domains/testing.md`
- `templates/debug-report.md`
- `checklists/debug-checklist.md`
- `checklists/delivery-checklist.md`

---

## Anti-Patterns

Avoid:
- adding the entire repository to always-on workspace rules
- mixing multiple behavior files without a clear primary mode
- treating domain files like style guides
- forcing heavy templates into fast interactive tasks
- skipping verification guidance when code edits are proposed

---

## Suggested Minimal Cursor Base

A practical minimal Cursor base is:
- `CLAUDE.md`
- `runtime/router.md`
- `runtime/conflict-resolution.md`

Then add per task:
- one behavior
- relevant domains
- one template if needed
- one or more checklists

This keeps the environment sharp without becoming noisy.

---

## Short Reminder

For Cursor, use:
- small stable workspace rules
- task-time overlays
- repo evidence over assumptions
- behavior-driven mode control
