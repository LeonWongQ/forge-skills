# Report: Incident Report

## Purpose

Use this report format when the task concerns a production issue, outage, reliability event, severe regression, or operational failure requiring root-cause-style reporting.

This report is useful for:
- incidents
- severe service regressions
- major flaky CI/system instability patterns
- postmortem-style technical summaries
- bug investigations with operational consequences

The goal is not merely to describe failure, but to explain:
- impact
- timeline
- root cause
- mitigation
- long-term prevention

---

## Report Structure

### 1. Incident summary
State the issue briefly.

Include:
- what failed
- affected system or flow
- high-level outcome

Example:
"Order summary responses served stale data after update under concurrent traffic because cache invalidation happened before transaction commit."

### 2. Impact
Describe:
- who or what was affected
- severity of operational effect
- data correctness, reliability, or latency consequences
- known scope

Examples:
- stale reads for recently updated orders
- intermittent checkout failure in CI only
- elevated DB load due to cache breakdown
- transaction timeouts under external API latency

### 3. Detection
Record how the issue was detected.

Examples:
- user reports
- failing alert
- CI failure
- error log spike
- support escalation
- manual investigation

### 4. Evidence timeline
Capture the sequence of meaningful observations.

This can be chronological or causal.

Examples:
1. deployment completed
2. stale-read reports appeared
3. logs showed update success without aligned cache refresh
4. code review identified invalidation before commit
5. no test covered rollback + read race path

### 5. Root cause
State the best-supported root cause.

Include:
- direct mechanism
- enabling condition(s)
- confidence
- important assumptions if any

Strong root-cause writing often includes:
- trigger
- mechanism
- amplifier
- detection gap

### 6. Mitigation / immediate response
Describe what was or should be done to reduce impact quickly.

Examples:
- disabled problematic code path
- moved invalidation to safer path
- added retry guard
- rolled back deployment
- isolated failing test

### 7. Long-term fix
Describe what should prevent recurrence.

Examples:
- transaction-aware post-commit invalidation
- regression test coverage
- better observability for prompt tool execution
- stronger fixture isolation in CI
- schema constraint to prevent race-driven duplicates

### 8. Verification
State how the mitigation/fix was or should be validated.

Examples:
- targeted regression test
- repeated concurrency scenario
- metrics stabilized after deployment
- traces no longer show timeout path

### 9. Remaining risks
List residual concerns.

Examples:
- alternate write path still unreviewed
- no high-concurrency load validation yet
- provider timeout behavior still partially unknown

### 10. Lessons learned
Capture durable insights.

Examples:
- invalidation timing must align with durable commit
- fixed waits in browser tests hide environment sensitivity
- model output must be schema-validated before tool invocation

---

## Style Guidance

- factual
- causally clear
- free of blame language
- explicit about uncertainty
- useful for prevention, not just description

---

## Good Fit Examples

Use this report for:
- production bug postmortem
- integration outage summary
- cache inconsistency incident
- severe test infrastructure instability review
- AI workflow failure affecting production behavior

---

## Avoid

Avoid using this report for:
- routine code review
- ordinary refactor planning
- simple non-operational debugging unless it needs incident-level treatment

---

## Short Reminder

Incident report means:
- what failed
- who/what was affected
- what the root cause was
- what was done
- how recurrence should be prevented
