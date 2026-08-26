# EXAMPLES.md

## Purpose

This file shows concrete task compositions and example operating flows.

It is intended to make the repository easy to use in real situations.

These are not strict recipes.
They are practical examples.

---

## Example 1: Review a Spring + Redis service

### User request
"Review this Spring Boot service that updates MySQL and invalidates Redis. I'm worried about stale reads and transaction issues."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `verification.md`
- `delivery.md`

#### Behavior
- `review.md`

#### Domains
- `java.md`
- `spring.md`
- `mysql.md`
- `redis.md`
- `testing.md`

#### Template
- `review-report.md`

#### Checklists
- `general-quality.md`
- `review-checklist.md`
- `verification-checklist.md`
- `delivery-checklist.md`

### Expected output style
- overall assessment
- prioritized findings
- stale-read / invalidation / transaction observations
- suggested fix direction
- open questions about invocation path or write coverage

---

## Example 2: Debug flaky Playwright modal test

### User request
"This Playwright test fails intermittently in CI when checking the modal."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `delivery.md`

#### Behavior
- `debug.md`

#### Domains
- `playwright.md`
- `testing.md`

#### Template
- `debug-report.md`

#### Checklists
- `general-quality.md`
- `debug-checklist.md`
- `delivery-checklist.md`

### Expected output style
- symptom summary
- evidence like weak locator or fixed wait
- ranked hypotheses
- likely cause
- validation path with trace review / repeat runs

---

## Example 3: Refactor a large Spring service

### User request
"Help me refactor this service class. It is hard to test and mixes too many concerns."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `planning.md`
- `execution.md`
- `verification.md`
- `delivery.md`

#### Behavior
- `refactor.md`

#### Domains
- `java.md`
- `spring.md`
- `testing.md`

#### Template
- `refactor-plan.md`

#### Checklists
- `general-quality.md`
- `refactor-checklist.md`
- `verification-checklist.md`
- `delivery-checklist.md`

### Expected output style
- refactor goal
- current structural problems
- phased transformation plan
- behavior-preservation strategy
- test/regression validation guidance

---

## Example 4: Explain Spring transaction self-invocation

### User request
"Explain why `@Transactional` doesn't work when one method in the same class calls another."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `context.md`
- `reasoning.md`
- `delivery.md`

#### Behavior
- `explain.md`

#### Domains
- `spring.md`
- `java.md`

#### Template
- `explanation.md`

#### Checklists
- `general-quality.md`
- `delivery-checklist.md`

### Expected output style
- what it is
- why it matters
- proxy mechanism
- example
- common misconception

---

## Example 5: Optimize a MySQL query path

### User request
"This endpoint becomes slow for large tenants. Here's the query and index definition."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `planning.md`
- `verification.md`
- `delivery.md`

#### Behavior
- `optimize.md`

#### Domains
- `mysql.md`
- `testing.md`

#### Template
- `implementation-plan.md`

#### Checklists
- `general-quality.md`
- `verification-checklist.md`
- `delivery-checklist.md`

### Expected output style
- likely bottleneck
- query/index mismatch reasoning
- recommended optimization path
- tradeoffs
- validation with `EXPLAIN` and representative workload

---

## Example 6: Review Spring AI tool-calling design

### User request
"Review this Spring AI workflow that lets the model call internal tools."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `verification.md`
- `delivery.md`

#### Behavior
- `review.md`

#### Domains
- `spring.md`
- `spring-ai.md`
- `java.md`
- `testing.md`

#### Template
- `review-report.md`

#### Checklists
- `general-quality.md`
- `review-checklist.md`
- `verification-checklist.md`
- `delivery-checklist.md`

### Expected output style
- safety concerns
- output validation observations
- prompt/tool boundary risks
- fallback and observability concerns
- recommended guardrails

---

## Example 7: Document a cache invalidation runbook

### User request
"Write an internal runbook for debugging cache invalidation issues in this service."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- `runtime/router.md`
- `discover.md`
- `evidence.md`
- `context.md`
- `reasoning.md`
- `delivery.md`

#### Behavior
- `document.md`
- `explain.md`

#### Domains
- `spring.md`
- `redis.md`
- `testing.md`

#### Template
- `default.md` or `explanation.md`

#### Checklists
- `general-quality.md`
- `delivery-checklist.md`

### Expected output style
- purpose
- symptoms
- likely causes
- step-by-step checks
- caveats
- escalation notes

---

## Example 8: Persistent review artifact

### User request
"Give me a reusable review summary for this PR."

### Composition

#### Kernel
- `CLAUDE.md`

#### Engine
- standard review path

#### Behavior
- `review.md`

#### Template
- `review-report.md`

#### Report
- `review-summary.md`

### Expected outcome
- conversational review response
- plus a condensed reusable summary artifact

---

## Example 9: Production incident artifact

### User request
"We had stale reads after deployment. Summarize the incident and proposed long-term fix."

### Composition

#### Kernel
- `CLAUDE.md`

#### Behavior
- `debug.md`
- `document.md`

#### Domains
- likely `spring.md`, `redis.md`, `mysql.md`, `testing.md`

#### Template
- `debug-report.md`

#### Report
- `incident-report.md`

### Expected outcome
- current best root-cause analysis
- impact summary
- mitigation
- long-term prevention

---

## Example 10: Minimal usage

### User request
"Quickly explain whether this code can return null unexpectedly."

### Composition

#### Kernel
- `CLAUDE.md`

#### Behavior
- `review.md` or `explain.md`

#### Domain
- `java.md`

#### Template
- `default.md`

#### Checklist
- `general-quality.md`

### Expected style
- short answer
- key evidence
- direct conclusion
- one next step if needed

---

## Practical Rule of Thumb

If you are unsure how to compose a task:

1. choose the primary behavior
2. choose only the domains that truly matter
3. use the smallest engine path that preserves correctness
4. pick the simplest useful template
5. always apply at least a general quality check

---

## Short Reminder

Examples are there to teach composition, not to freeze it.
Use them as patterns, not rigid scripts.
