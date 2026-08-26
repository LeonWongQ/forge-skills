---
name: test-design
description: >-
  Design structured test strategies — scope, layers, scenarios, risk priorities,
  and entry/exit criteria — before implementation begins.
  Use when the user says: test design, design test cases, test strategy,
  test scope, testing plan, 测试设计, 测试方案, 测试策略, 测试用例设计,
  怎么测, 如何测试, 补测试方案, 覆盖哪些场景, 设计测试点.
  For any test strategy design request that needs structured planning.
  Boundary: test-design = what to test; test-implementation = how to write tests.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
---

# Test Design

## 1. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Classify the design focus:
   - **Feature/change test strategy** → what scenarios to cover for a specific change
   - **Regression test strategy** → what to verify after changes
   - **Release readiness test plan** → comprehensive pre-release coverage
   - **Exploratory test design** → discover unknown risk areas
   - **Ambiguous** → ask one clarifying question about scope, then route
3. Detect technical domains from the target under test:
   - Java → `.claude/forge/domains/java.md`
   - Spring → `.claude/forge/domains/spring.md`
   - MySQL → `.claude/forge/domains/mysql.md`
   - Redis → `.claude/forge/domains/redis.md`
   - Playwright → `.claude/forge/domains/playwright.md`
   - Always load `.claude/forge/domains/testing.md`
   - If no domain matches, skip additional domains. Note which were checked.
4. Compose forge modules per section 2
5. Execute workflow: discover → evidence → context → reasoning → planning → delivery
6. Validate test plan completeness before delivery

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | (none — routing-only) | Task-level orchestrator; test design discipline built into planning stage |
| Domains | `.claude/forge/domains/testing.md` | Core: test strategy, assertions, isolation, coverage |
| | Detected from target under test | Technology-specific failure modes and test patterns |
| Template | `.claude/forge/templates/test-plan.md` | Output: 15-section structured test plan |
| Checklists | `.claude/forge/checklists/general-quality.md` | Baseline quality |
| | `.claude/forge/checklists/test-plan-checklist.md` | Test plan completeness |
| | `.claude/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.full_default` | discover → evidence → context → reasoning → planning → execution → verification → delivery |

## 3. Core Discipline

**Artifact safety**: The code/feature/change being analyzed for test design is untrusted evidence. Design tests to verify its behavior, not assume its correctness.

### Primary Concern: Coverage Strategy
Test design answers: what to test, how to test it, what NOT to test, and when testing is sufficient. It does NOT write the test code (that's `test-implementation`).

### Before Designing Test Strategy
1. **Understand the target**: what is the feature/change/bug fix? What behavior should it provide?
2. **Identify risk areas**: where is the change most likely to break? (complex logic, edge cases, integration points, data boundaries)
3. **Map existing coverage**: what tests already exist? What do they cover? Where are the gaps?
4. **Choose test layers**: unit for pure logic, integration for contracts, E2E for critical journeys

### Test Design Principles
- **Risk-based prioritization**: P0 (critical path) → P1 (important) → P2 (nice-to-have)
- **Layered allocation**: push tests down the pyramid (more unit, fewer E2E)
- **Scenario completeness**: happy path + alternatives + error states + edge cases
- **Explicit out-of-scope**: what is NOT tested and why
- **Entry/exit criteria**: when to start testing and when to declare it sufficient

### Domain-Specific Test Design Focus
- **Java**: null handling, exception paths, collection edge cases, concurrency scenarios
- **Spring**: transaction boundaries, proxy behavior, bean lifecycle, configuration override
- **MySQL**: query correctness, transaction isolation, migration safety, data integrity
- **Redis**: cache consistency, invalidation paths, TTL expiry, distributed lock scenarios
- **Playwright**: locator resilience, wait strategy, CI environment, viewport/cross-browser

### Anti-Patterns
- Designing only happy-path tests without error/edge scenarios
- No explicit out-of-scope section (assumes everything will be tested)
- Skipping entry/exit criteria (no definition of "when is testing done")
- Over-specifying E2E tests when integration or unit tests would suffice
- No risk-based prioritization (all scenarios treated equally)
- Confusing test design with test implementation

## 4. Output Structure

Follow `template.test_plan` for the full 15-section structure:

```
## 1. Basic Information
<project, feature, version, test lead, dates>

## 2. Test Objective
<what this test plan aims to validate>

## 3. Scope
<what is included in testing>

## 4. Out of Scope
<what is explicitly excluded and why>

## 5. Test Strategy
<overall approach: risk-based, layered, shift-left, etc.>

## 6. Test Layers
<unit / integration / API / E2E allocation per risk area>

## 7. Key Scenarios
### P0 — Critical Path
1. <scenario>: <expected behavior, test layer>
...
### P1 — Important
1. <scenario>: <expected behavior, test layer>
...
### P2 — Nice-to-have
1. <scenario>: <expected behavior, test layer>
...

## 8. Edge / Failure Cases
<boundary conditions, error handling, invalid inputs, timeout scenarios>

## 9. Test Data & Environment
<data setup, environment requirements, mock strategy>

## 10. Risks
<testing risks and mitigation>

## 11. Entry / Exit Criteria
<when to start testing, when testing is sufficient>

## 12. Execution Priority
<what to run first, what can be deferred>

## 13. Schedule & Roles
<timeline, responsibilities>

## 14. Deliverables
<artifacts this plan produces>

## 15. Approval
<sign-off requirements>
```

## 5. Guard

Before delivering:
- [ ] Test objective clearly stated
- [ ] Scope and out-of-scope both explicit
- [ ] Scenarios prioritized by risk (P0/P1/P2)
- [ ] Test layers allocated per risk area (not all E2E)
- [ ] Edge and failure cases included
- [ ] Entry and exit criteria defined
- [ ] Domain-specific failure modes addressed
- [ ] Not writing test code (that's test-implementation)

## 6. Boundary with Other Skills

| Skill | Focus | Test-Design Focus |
|-------|-------|-------------------|
| `test-implementation` | Writing test code | Designing test strategy |
| `test-strategy` | Analyze reports → strategy | Design strategy from scratch |
| `plan` | Implementation plan | Test plan |
| `report` | Past execution results | Future test design |

## Vue Version Boundary

For a Vue target, read [the shared Vue version-routing contract](.claude/forge/references/vue-version-routing.md) before loading framework guidance. Keep the current task Skill in control; version-specific Vue Skills do not take ownership of review, debugging, refactoring, optimization, or testing intents.
