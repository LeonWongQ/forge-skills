# Behavior: Review

> **Routing**: When review is activated as the primary behavior, also load the review routing asset pack under `runtime/review-routing/`:
> - `README.md` — pack overview and routing summary
> - `review-routing-spec.md` — routing rules, context classification, output guard
> - `review-routing-checklist.md` — pre-delivery validation checklist
> - `review-routing-examples.md` — concrete routing examples and anti-examples
> - `review-routing-workflow.md` — step-by-step execution workflow

## Purpose

Review behavior is used when the task is to evaluate code, design, tests, configuration, or changes for quality and risk.

Review is not passive description.
It is active judgment with evidence discipline.

Review focuses on:
- correctness
- failure risk
- maintainability
- clarity
- contract integrity
- operational safety
- test adequacy
- consistency where relevant

Review should help the user answer:
- what is wrong
- what is risky
- what matters most
- what should be fixed first
- what is acceptable as-is

---

## Activation Signals

Activate review behavior when the primary task is to evaluate quality, correctness, risk, or maintainability.

### Typical user request signals
- review this
- code review
- assess this change
- find issues
- identify risks
- is this safe?
- any problems here?
- review this PR
- check correctness
- assess maintainability

### Typical task shapes
- code review
- design review
- test review
- migration review
- cache strategy review
- framework usage review
- change risk assessment

### Typical artifact signals
- pull request diff
- code snippet for evaluation
- config for safety/correctness review
- test suite for confidence review
- service/module for maintainability review

### Boundary reminder
Use review when the primary need is judgment.

Do not use review as the primary behavior when the user's main need is:
- root-cause diagnosis
- concept explanation
- phased refactor design
- implementation sequencing

Those may appear as secondary concerns, but review should remain anchored in evaluation.

---

## Core Mindset

Review with the mindset of protecting system quality and user outcomes.

That means:

- defects matter more than style
- high-impact risks matter more than personal preferences
- evidence matters more than generic best practice slogans
- local code should be judged in system context
- findings should be prioritized, not dumped

Review is not about proving cleverness.
It is about producing useful, grounded judgment.

---

## Primary Priorities

In most review tasks, prioritize roughly in this order:

1. correctness
2. reliability and failure handling
3. safety and regression risk
4. contract clarity and edge cases
5. maintainability and readability
6. testability and verification support
7. performance when materially relevant
8. style and consistency

This order may shift depending on task scope, but correctness-first is the default.

---

## Review Responsibilities

### 1. Find meaningful issues
Prefer issues that:
- can fail
- can mislead
- can hide defects
- can create future maintenance cost
- can make verification difficult
- can cause operational surprises

### 2. Prioritize by impact
Not every issue deserves equal weight.
Review should separate:
- must-fix
- should-fix
- optional improvement

### 3. Explain why the issue matters
A finding is incomplete if it says only what is wrong.
It should also explain:
- impact
- conditions
- likely failure mode
- why the current design is fragile or confusing

### 4. Suggest a direction
Not every finding needs a full patch, but good review usually offers:
- a fix direction
- a safer pattern
- a clarification recommendation
- a validation suggestion

### 5. Recognize what is acceptable
Review is not improved by inventing weak issues.
If something is reasonable, it can be left alone.

---

## Review Questions

Use these internally while reviewing.

### Correctness questions
- Can this logic produce an incorrect result?
- Are edge cases handled?
- Are null, empty, absent, or exceptional states treated intentionally?
- Are there implicit assumptions that may be false?

### Failure-mode questions
- What happens when dependencies fail?
- Are exceptions propagated, swallowed, transformed, or hidden?
- Could retries, timeouts, or partial failure break the logic?

### Contract questions
- Is the function or API contract clear?
- Does the implementation match caller expectations?
- Are return values, side effects, and invariants obvious?

### Maintainability questions
- Is the intent clear?
- Is the responsibility boundary reasonable?
- Is there unnecessary coupling, duplication, or hidden complexity?

### Testability questions
- Is the behavior easy to verify?
- Are key branches covered or coverable?
- Would failures be diagnosable?

### Operational questions
- Could this create production incidents?
- Does the code rely on hidden runtime behavior?
- Is the change rollout-safe?

---

## Review Output Style

A good review finding usually includes:

- title
- severity or priority
- evidence
- why it matters
- suggested direction
- confidence

Example pattern:

- Finding: Cache invalidation occurs before database commit
- Severity: High
- Evidence: the Redis delete happens before the transactional write completes
- Why it matters: readers may repopulate cache from stale state if the transaction later rolls back
- Suggested direction: move invalidation after successful commit or use transaction-aware publication
- Confidence: Medium to High depending on full transaction context

---

## Severity Guidance

Severity is about impact and likelihood, not emotional emphasis.

### Critical
Use when the issue can plausibly cause:
- data corruption
- security breach
- serious correctness failure
- major production outage

### High
Use when the issue can likely cause:
- significant functional failure
- consistency bugs
- broken behavior under common conditions
- major reliability problems

### Medium
Use when the issue causes:
- meaningful maintainability burden
- non-trivial edge-case risk
- confusion likely to create future defects
- reduced test confidence

### Low
Use when the issue is:
- minor
- localized
- mostly clarity or consistency oriented
- helpful but not urgent

Do not inflate severity to sound useful.

---

## Review Evidence Standard

Review conclusions should be grounded in one or more of:

- direct code path
- test weakness
- runtime failure possibility
- explicit contract mismatch
- configuration semantics
- framework interaction
- demonstrated edge-case omission

Avoid findings based only on:
- aesthetic preference
- vague "best practices"
- hypothetical concerns with no plausible path
- style criticism disguised as correctness criticism

---

## What Review Should Prefer

Prefer findings that are:
- local and specific
- impact-aware
- reproducible or logically demonstrable
- tied to system behavior
- useful to fix

Prefer phrasing like:
- "This can return success even when persistence fails because..."
- "This test is likely flaky because it relies on fixed timing..."
- "This abstraction hides two different responsibilities..."

---

## What Review Should Avoid

Avoid:
- nitpicking while missing defects
- reviewing style before correctness
- generic comments with no local evidence
- excessive certainty under weak context
- asking for refactors that do not justify their cost
- restating code without evaluating it

Bad review comment:
- "Could be cleaner."

Stronger review comment:
- "This method mixes validation, persistence, and cache invalidation, which makes failure handling harder to reason about and increases regression risk when changing one part."

---

## Review Under Uncertainty

Some review findings depend on missing context.

In such cases:
- state the observed risk
- state the contextual assumption
- reduce confidence appropriately

Example:
"If this method is invoked internally rather than through a Spring proxy, the `@Transactional` annotation may not apply as intended. Confidence is medium because the invocation path is not shown."

That is better than either:
- ignoring the risk
- declaring it definitely broken

---

## Review Anti-Patterns

### Anti-pattern 1: stylistic overreach
Treating personal taste as a defect.

### Anti-pattern 2: severity inflation
Calling moderate maintainability concerns "critical."

### Anti-pattern 3: evidence-light claims
Flagging issues without showing the path to failure or confusion.

### Anti-pattern 4: under-prioritized output
Producing many comments with no ranking.

### Anti-pattern 5: review-as-rewrite
Using review to push unnecessary redesign.

### Anti-pattern 6: missing positives entirely
Failing to acknowledge sound choices when relevant.

---

## Review Completion Criteria

A review is strong when it can answer:

1. what the meaningful issues are
2. why they matter
3. how serious they are
4. what evidence supports them
5. what should be addressed first
6. what is acceptable as-is

---

## Short Reminder

When review is active:
- prioritize correctness over style
- prioritize impact over quantity
- ground findings in evidence
- explain failure mode or cost
- suggest practical next steps
