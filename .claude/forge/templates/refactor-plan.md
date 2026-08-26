# Template: Refactor Plan

## Purpose

Use this template when the primary task is refactoring.

This template is designed for outputs that must communicate:
- structural problems
- refactor goals
- phased transformations
- behavior-preservation strategy
- risks
- validation path

It is appropriate for:
- service cleanup
- responsibility decomposition
- complexity reduction
- testability improvement
- duplication reduction
- phased structural modernization

---

## Output Structure

### 1. Refactor goal
State the structural objective clearly.

Examples:
- separate validation, persistence, and cache coordination concerns
- reduce duplication across similar service methods
- isolate business rules from framework side effects
- improve testability of decision logic

### 2. Current structural problems
List the real problems being addressed.

Examples:
- method mixes unrelated responsibilities
- side effects are interleaved with decision logic
- hidden dependencies make testing hard
- duplication causes inconsistent behavior
- control flow is difficult to reason about

### 3. Proposed refactor strategy
Summarize the preferred approach.

Examples:
- incremental extraction
- seam creation before larger decomposition
- isolate pure logic first
- preserve public API while reducing internal coupling

### 4. Step-by-step transformation plan
List ordered steps.

For each step include:
- intended change
- structural benefit
- important caution or dependency
- optional verification note

Example:
1. Extract pure validation logic into helper to reduce side-effect coupling
2. Move persistence orchestration into dedicated method
3. Isolate post-commit cache/event handling path
4. Remove duplicated branching after parity is verified

### 5. Behavior-preservation controls
State how external behavior will be protected.

Examples:
- preserve method signatures
- preserve side-effect order
- compare before/after scenario tests
- keep transaction boundary unchanged in first phase

### 6. Risks and constraints
List:
- weak test coverage
- framework lifecycle sensitivity
- transaction ordering risk
- public contract stability requirement
- limited verification environment

### 7. Verification plan
State how the refactor should be checked.

Examples:
- regression tests
- scenario comparison
- contract-level assertions
- side-effect ordering tests
- integration checks around transactional behavior

### 8. Non-goals
Explicitly state what this refactor will not attempt.

Examples:
- not redesigning caching strategy
- not changing API shape
- not merging semantically different flows
- not introducing new architecture layers unless needed

---

## Style Guidance

- emphasize structure, not just code motion
- preserve behavior unless explicitly changing it
- keep the plan incremental when possible
- highlight safety controls
- avoid rewrite rhetoric unless justified

---

## Good Fit Examples

Use this template for:
- refactoring a large service
- splitting mixed responsibilities
- making logic easier to test
- reducing duplication safely
- improving module boundaries

---

## Avoid

Avoid using this template when the task is primarily:
- code review findings only
- incident/root-cause investigation
- feature implementation planning
- simple explanation

---

## Short Reminder

Refactor plan means:
- structural goal
- real current problems
- phased safe change plan
- behavior-preservation strategy
- verification
