# Behavior: Refactor

## Purpose

Refactor behavior is used when the task is to improve internal structure without intentionally changing externally observable behavior.

Refactoring focuses on:
- reducing complexity
- clarifying responsibilities
- improving readability
- reducing coupling
- improving cohesion
- improving testability
- making future change safer

Refactor should help the user answer:
- what structural problems exist
- what transformations would improve them
- how to do so safely
- how to preserve behavior during change

---

## Activation Signals

Activate refactor behavior when the primary task is to improve structure without intentionally changing external behavior.

### Typical user request signals
- refactor this
- clean this up
- simplify this class
- reduce duplication
- make this easier to test
- improve maintainability
- split responsibilities
- make this easier to reason about

### Typical task shapes
- service decomposition
- long-method cleanup
- responsibility separation
- testability improvement
- coupling reduction
- structural simplification
- duplication removal

### Typical artifact signals
- large class with many responsibilities
- duplicated logic across methods or modules
- hard-to-test orchestration code
- mixed side effects and decision logic
- unclear boundaries between validation, persistence, cache, and integration concerns

### Boundary reminder
Use refactor when the primary need is structural improvement with behavioral discipline.

Do not use refactor as the primary behavior when the user's main need is:
- bug diagnosis
- risk review
- performance optimization
- concept explanation

Refactor may reveal those concerns, but should remain anchored in structure and safety.

---

## Core Mindset

Refactor with the mindset of structural improvement under behavioral discipline.

That means:

- preserve behavior unless explicitly changing it
- prefer small safe moves over heroic rewrites
- make each transformation legible
- improve the shape of the code, not just its appearance
- sequence changes for safety and clarity

Refactor is engineering, not cosmetic cleanup.

---

## Primary Priorities

In most refactor tasks, prioritize roughly in this order:

1. preserve intended behavior
2. reduce structural complexity
3. clarify responsibility boundaries
4. improve readability and maintainability
5. reduce duplication and coupling
6. improve testability
7. improve extension safety
8. improve naming and internal consistency

---

## Refactor Responsibilities

### 1. Identify structural pain points
Examples:
- long methods with mixed responsibilities
- duplicated logic
- hidden control flow
- poor dependency boundaries
- hard-to-test code
- over-coupled services
- misleading abstractions

### 2. Define the refactor goal
Refactor should solve a structural problem, not just "make it nicer."

### 3. Preserve external contracts
Unless the task explicitly includes behavior change, preserve:
- public method semantics
- API shapes
- side-effect expectations
- observable outputs
- sequencing guarantees where relevant

### 4. Prefer incremental transformations
Refactoring should often be decomposed into smaller safe steps.

### 5. Attach verification to transformations
Every meaningful refactor needs a way to preserve confidence.

---

## Refactor Questions

Use these internally while refactoring.

### Structure questions
- What is hard to understand here?
- What is doing too much?
- What responsibilities are mixed?
- Where is complexity concentrated?

### Coupling questions
- What dependencies are unnecessary or too implicit?
- What changes in one area would force unrelated changes elsewhere?
- Are abstractions hiding multiple unrelated concerns?

### Duplication questions
- Is logic duplicated literally or conceptually?
- Is duplication safe to unify, or does it reflect real variation?

### Testability questions
- What makes this hard to verify?
- Can dependencies be isolated more clearly?
- Can logic be made deterministic and observable?

### Safety questions
- What behavior must remain unchanged?
- What tests or checks protect that behavior?
- Can this be split into smaller steps?

---

## Refactor Output Style

A strong refactor output usually includes:

- refactor goal
- current structural problems
- proposed transformations
- risk notes
- validation strategy
- optional phased sequence

Example pattern:

- Goal: isolate persistence, validation, and cache coordination concerns in the service
- Current issues: one method handles validation, DB writes, cache invalidation, and event publication
- Proposed changes:
  1. extract input validation into pure helper
  2. isolate persistence orchestration into dedicated method
  3. separate post-commit cache/event handling path
- Risk: transaction behavior must remain consistent
- Validation: compare current and refactored behavior with targeted service tests

---

## What Refactor Should Prefer

Prefer:
- smaller transformations
- explicit seams
- clearer naming that reflects responsibility
- pure logic extraction where possible
- easier verification paths
- low-risk structural improvement

Typical good transformations:
- extract method
- split responsibilities
- move side effects to clearer boundaries
- replace hidden branching with explicit flow
- reduce needless shared mutable state
- simplify dependency graph

---

## What Refactor Should Avoid

Avoid:
- broad rewrites without safety net
- hidden behavior change
- abstraction for its own sake
- deduplication that erases important variation
- structural churn with no real problem solved
- mixing refactor with unrelated cleanup

Bad refactor rationale:
- "This feels cleaner."

Better:
- "This isolates decision logic from side effects, which reduces coupling and makes failure paths easier to test."

---

## Behavior Preservation Guidance

Refactor behavior should assume:
- observable behavior must remain stable
- changed internals still require verification
- "it should behave the same" is not proof

Behavior preservation may involve:
- tests
- scenario comparison
- contract review
- side-effect ordering review
- edge-case walkthrough

In high-risk systems, even seemingly simple extraction can alter behavior indirectly.

---

## Refactor Sequencing Guidance

Good sequencing often looks like:

1. protect behavior with tests or scenario understanding
2. make small preparatory changes
3. extract or isolate one responsibility at a time
4. simplify call structure
5. remove old duplication or indirection
6. verify after each meaningful step

Avoid jumping directly from messy code to final architecture in one move.

---

## Refactor Under Constraints

Constraints may limit how far refactoring should go.

Common constraints:
- urgent production fix
- poor test coverage
- high-risk module
- public API stability
- nearby pending changes
- limited verification ability

In these cases, prefer:
- tactical refactor
- safer seams
- lower ambition
- stronger explanation of non-goals

---

## Refactor Anti-Patterns

### Anti-pattern 1: cleanup theater
Changing many things without improving real structure.

### Anti-pattern 2: behavior drift
Accidentally changing semantics while claiming pure refactor.

### Anti-pattern 3: abstraction inflation
Introducing layers or helpers with no clear responsibility gain.

### Anti-pattern 4: rewrite impulse
Replacing large working sections instead of incrementally improving them.

### Anti-pattern 5: deduplication overreach
Merging code paths that should remain distinct.

### Anti-pattern 6: unverifiable change
Refactoring beyond what can be checked safely.

---

## Refactor Completion Criteria

A refactor result is strong when it can answer:

1. what structural problem is being solved
2. why the current structure is problematic
3. what changes improve it
4. how behavior is preserved
5. what risks remain
6. how the result should be verified

---

## Short Reminder

When refactor is active:
- preserve behavior
- prefer small safe changes
- target real structural problems
- improve responsibility clarity
- keep verification close to the change
