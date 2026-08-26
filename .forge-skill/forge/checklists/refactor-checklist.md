# Checklist: Refactor

## Purpose

Use this checklist when refactor behavior is active.

It verifies that structural improvement is real and behavior preservation is respected.

---

## Core Checks

- Is the structural problem clearly identified?
- Is the refactor goal explicit?
- Is external behavior preservation treated seriously?
- Are proposed changes incremental where possible?
- Are responsibility boundaries improved?
- Is unnecessary abstraction avoided?
- Are risks or weak coverage areas visible?
- Is there a verification strategy for preserved behavior?
- Are non-goals or scope limits clear when needed?
- Does the plan improve maintainability rather than merely move code around?

---

## Safety Checks

- Could the refactor accidentally change contract or side-effect ordering?
- Is there an adequate way to detect regressions?
- Are hidden framework/lifecycle interactions considered if relevant?

---

## Failure Signals

If several answers are "no", the refactor result may suffer from:
- cleanup theater
- rewrite impulse
- hidden behavior drift
- abstraction inflation
- weak safety discipline
