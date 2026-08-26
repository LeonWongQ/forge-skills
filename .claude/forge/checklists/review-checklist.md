# Checklist: Review

## Purpose

Use this checklist when review behavior is active.

It verifies that review output is meaningful, prioritized, and evidence-based.

---

## Core Checks

- Were the findings prioritized rather than presented as an undifferentiated list?
- Were correctness and failure risks considered before style?
- Does each meaningful finding explain why it matters?
- Is severity proportional to impact and likelihood?
- Are findings grounded in direct code/config/test/runtime observations?
- Are weak or speculative findings clearly qualified?
- Are suggested fixes or directions practical?
- Were edge cases, contract assumptions, and failure paths considered?
- Were testability or verification implications noted when relevant?
- Are non-issues left alone rather than over-reviewed?

---

## Finding Quality Checks

For each major finding:

- Is the finding specific?
- Is the evidence clear?
- Is the impact explained?
- Is the severity justified?
- Is a next action suggested?

---

## Failure Signals

If several answers are "no", the review may suffer from:
- nitpicking
- severity inflation
- evidence-light judgment
- poor prioritization
- low practical value
