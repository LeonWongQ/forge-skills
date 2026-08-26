# Forge Skills

<!-- forge-facts: skills=31 -->

This directory contains the project-owned Skill entrypoints. Each Skill routes one task family into the smallest useful Forge behavior, domain, workflow, template, and checklist composition.

## Design Contract

- `SKILL.md` contains discovery metadata, routing decisions, essential constraints, and links to conditional detail.
- `references/` contains mode-specific methods loaded only when that mode applies.
- `scripts/` contains deterministic helpers when repeated execution is safer than regenerated commands.
- `agents/openai.yaml` contains user-facing metadata.
- Shared engineering behavior stays in `.claude/forge`; a Skill should not duplicate the kernel, generic report templates, or broad checklists.

The quality gate enforces English explanatory bodies, valid metadata and references, registry coverage, and a 220-line maximum for each `SKILL.md` entrypoint.

## Inventory

General engineering:

`architecture-design`, `code-review`, `contract-compatibility`, `data-design`, `debug`, `dependency-audit`, `document`, `error-analysis`, `explain`, `explore`, `implement`, `incident`, `migration`, `optimize`, `plan`, `refactor`, `release-readiness`, `report`, `security-review`.

Testing and evaluation:

`llm-evaluation`, `page-test`, `test-design`, `test-implementation`, `test-strategy`.

Framework and platform:

`bailian-api`, `bailian-workflow`, `vite-vue3`, `vue2`, `vue2-7`.

Operations:

`auto-compact`, `forge`.

The machine-readable source of truth is `.claude/forge/registry/skills.json`; do not maintain a second routing model in this document.

## Installation

Use the common installer documented in the repository root. It supports Codex, Claude, and Cursor at global or project scope. Existing same-name paths are preserved as conflicts rather than overwritten.
