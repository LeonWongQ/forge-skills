---
name: plan
description: >-
  Create structured implementation plans, refactor plans, rollout strategies,
  technical execution plans, feature plans, and migration plans with domain-aware
  step sequencing, risk identification, and validation strategy.
  Use when the user says: create a plan, implementation plan, how should I implement,
  plan this feature, plan this refactor, plan the rollout, design the implementation,
  technical plan, tech plan, plan the changes, how would you build, help me plan,
  create a refactor plan, plan the migration,
  方案, 计划, 实施方案, 重构方案, 帮我规划, 怎么做, 如何实现, 设计一下.
  For any planning or design request that needs structured execution steps.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch, Write]
---

# Plan

## 1. Activation Sequence

1. Load forge kernel: `.forge-skill/forge/CLAUDE.md`, `.forge-skill/forge/AUTOLOAD.md`
2. Classify plan type (see section 2)
3. Detect technical domains from codebase context:
   - Java project → `.forge-skill/forge/domains/java.md`
   - Spring annotations → `.forge-skill/forge/domains/spring.md`
   - Database/SQL → `.forge-skill/forge/domains/mysql.md`
   - Cache/Redis → `.forge-skill/forge/domains/redis.md`
   - Test code → `.forge-skill/forge/domains/testing.md`
   - If no clear domain signal, skip domain loading. Proceed with template + checklists only.
4. Compose forge modules per section 3
5. Execute full workflow: discover → evidence → context → reasoning → planning → delivery
6. Validate plan structure before delivery

## 2. Plan Type Selection

| User Intent | Template | Behavior |
|-------------|----------|----------|
| New feature, implementation, rollout, migration | `.forge-skill/forge/templates/implementation-plan.md` | General (task-level) |
| Structural improvement, redesign, cleanup, modernization | `.forge-skill/forge/templates/refactor-plan.md` | `.forge-skill/forge/behaviors/refactor.md` |
| Unclear | Ask: "Is this a new implementation or a refactoring of existing code?" |

See `.forge-skill/skills/plan/references/type-selection.md` for detailed decision guide.

## 3. Forge Module Composition

### For implementation plans:
| Module | Path |
|--------|------|
| Template | `.forge-skill/forge/templates/implementation-plan.md` |
| Checklists | `.forge-skill/forge/checklists/general-quality.md`, `.forge-skill/forge/checklists/verification-checklist.md`, `.forge-skill/forge/checklists/delivery-checklist.md` |
| Workflow | `workflow.full_default` |

Note: Implementation plans are task-level orchestrators — they have no single primary behavior. The plan skill itself provides the thinking discipline (structured decomposition, risk-aware sequencing, verification-first planning).

### For refactor plans:
| Module | Path |
|--------|------|
| Behavior | `.forge-skill/forge/behaviors/refactor.md` |
| Template | `.forge-skill/forge/templates/refactor-plan.md` |
| Checklists | `.forge-skill/forge/checklists/general-quality.md`, `.forge-skill/forge/checklists/refactor-checklist.md`, `.forge-skill/forge/checklists/verification-checklist.md`, `.forge-skill/forge/checklists/delivery-checklist.md` |
| Workflow | `workflow.full_default` |

### Always add domains detected from codebase.

## 4. Core Discipline

### Implementation Plan Discipline
- Start with the **objective**: what outcome the plan delivers
- State **assumptions and constraints** explicitly (what you assume to be true, what limits exist)
- Break work into **ordered, verifiable steps** — each step should produce a testable intermediate state
- Identify **risks** per step: what could go wrong, mitigation
- Include a **validation plan**: how to confirm the implementation works end-to-end
- Scope: what is IN and what is intentionally OUT

### Refactor Plan Discipline (from refactor.md)
- **Behavior preservation is the primary constraint** — the system must work the same way after refactoring
- **Minimal viable change** — prefer narrow, safe transformations over broad rewrites
- **Each step must be independently verifiable** — you should be able to test after each step
- **Phased sequencing**: safe foundational changes → core refactor → cleanup
- Identify current structural problems before proposing solutions

## 5. Output Structure

### Implementation Plan
```
## Objective
## Assumptions and Constraints
## Proposed Approach (1 paragraph)
## Implementation Steps
  1. <step>: what, why, verification, risk
  2. ...
## Risks and Mitigations
## Validation Plan
## Scope (in / out)
```

### Refactor Plan
```
## Current State Problems
## Target Structure
## Transformation Steps (phased)
  Phase 1: <safe foundations>
  Phase 2: <core refactor>
  Phase 3: <cleanup>
## Behavior Preservation Strategy
## Risks
## Validation Plan
```

## 6. Guard

Before delivering:
- [ ] Plan type correctly selected (impl vs refactor)
- [ ] Objective is clear and bounded
- [ ] Steps are ordered and each is verifiable
- [ ] Assumptions stated explicitly
- [ ] Risks identified with mitigations
- [ ] Validation plan included
- [ ] Scope (in/out) is explicit
- [ ] **Output**: Default to inline display. Write to file only with explicit user confirmation. Default output path: `plans/<plan-name>.md`.
