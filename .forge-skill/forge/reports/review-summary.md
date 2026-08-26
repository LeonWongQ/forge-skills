# Report: Review Summary

## Purpose

Use this report format when a review needs a compact but reusable summary rather than a full per-finding report.

This report is useful for:
- PR summary
- architecture review snapshot
- design review wrap-up
- management or team-facing review digest
- stored outcome of a broader detailed review

The goal is to preserve the highest-value review conclusions in a concise structure.

---

## Report Structure

### 1. Overall assessment
State the high-level review outcome.

Examples:
- safe with minor improvements
- functionally sound but structurally weak
- not recommended for merge until high-risk issues are fixed
- good direction with incomplete verification

### 2. Critical findings
List only the highest-priority issues.

For each item include:
- finding
- short impact statement
- confidence

### 3. Important improvements
List meaningful but not blocking improvements.

These may include:
- maintainability concerns
- test coverage gaps
- moderate edge-case risks
- performance improvements

### 4. Low-priority suggestions
Optional section for non-urgent improvements.

### 5. Positives
Highlight solid design or implementation choices worth preserving.

Examples:
- clear service/repository separation
- good scenario coverage in integration tests
- strong prompt observability pattern
- safe use of post-commit eventing

### 6. Recommendation
End with a clear action recommendation.

Examples:
- merge after fixing high-severity invalidation issue
- safe to proceed, but add regression test before rollout
- do not proceed until root cause is confirmed
- refactor can be deferred; correctness fix should go first

---

## Style Guidance

- brief
- prioritized
- decision-oriented
- fair
- useful to readers who do not need every detail

---

## Good Fit Examples

Use this report for:
- leadership summary of a detailed review
- team digest of a code review
- stored summary for future follow-up
- review handoff note

---

## Avoid

Avoid using this report for:
- primary root-cause reporting
- full refactor planning
- implementation sequence design
- deep conceptual explanation

---

## Short Reminder

Review summary means:
- overall judgment
- top issues
- meaningful improvements
- recommendation
