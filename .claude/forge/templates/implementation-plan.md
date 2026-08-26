# Template: Implementation Plan

## Purpose

Use this template when the primary task is to propose or organize implementation work.

This template is designed for outputs that must communicate:
- target outcome
- assumptions and constraints
- ordered build steps
- risks
- validation strategy

It is appropriate for:
- new feature implementation planning
- bug-fix implementation planning
- optimization rollout planning
- migration or integration planning
- scoped technical execution plans

---

## Output Structure

### 1. Objective
State the desired outcome in concrete terms.

Examples:
- add cache invalidation after successful updates
- introduce structured output validation for model responses
- optimize this query path for large tenant datasets

### 2. Assumptions and constraints
List what the plan depends on.

Examples:
- all writes pass through this service
- backward compatibility is required
- current schema cannot change in phase one
- no production load-test environment is available

### 3. Proposed approach
Summarize the selected direction before listing steps.

### 4. Ordered implementation steps
For each step include:
- action
- rationale
- dependency if relevant
- risk note if relevant

Example:
1. Add explicit post-commit invalidation hook
2. Introduce regression test for stale-read scenario
3. Verify no alternate write path bypasses invalidation
4. Add temporary logging to observe invalidation timing in staging

### 5. Risks
List important technical or delivery risks.

Examples:
- hidden write path bypass
- incomplete transaction context
- rollout coordination with existing consumers
- limited test environment realism

### 6. Validation plan
State how to confirm the implementation works.

Examples:
- targeted tests
- scenario walkthrough
- metrics/log review
- rollout observation
- regression checks

### 7. Follow-up opportunities
Optional section for non-essential improvements discovered during planning.

Examples:
- later refactor to isolate cache coordination logic
- future index refinement after metrics
- additional documentation after rollout

---

## Style Guidance

- outcome first
- steps should be actionable
- assumptions should be visible
- validation must be explicit
- avoid mixing implementation plan with full review report

---

## Good Fit Examples

Use this template for:
- feature plan
- bug-fix rollout plan
- integration implementation plan
- optimization implementation sequence
- staged technical work outline

---

## Avoid

Avoid using this template when the task is primarily:
- root cause diagnosis
- formal review findings
- pure refactor planning
- conceptual teaching

---

## Short Reminder

Implementation plan means:
- target outcome
- assumptions
- ordered actions
- risks
- validation
