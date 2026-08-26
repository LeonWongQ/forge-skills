# Report: Task Report

## Purpose

Use this report format when a task needs a persistent, reusable engineering record rather than only a conversational response.

This report is useful for:
- substantial analysis tasks
- implementation planning summaries
- review outcomes that should be stored
- refactor proposals
- multi-step technical investigations
- work handoff between engineers

The goal is to capture not only the answer, but also the framing, reasoning, and next steps in a reusable form.

---

## Report Structure

### 1. Task
State the task clearly.

Include:
- original objective
- primary requested outcome
- important framing assumptions

Example:
"Review the Spring Boot caching flow for consistency risks and propose the safest remediation sequence."

### 2. Scope
Define:
- what was analyzed
- what was intentionally excluded
- whether the work was broad or targeted

Example:
"In scope: cache invalidation flow in the order update path. Out of scope: global cache strategy redesign."

### 3. Active behavior(s)
Record the active behavior mode(s).

Examples:
- review
- debug
- refactor
- optimize
- explain

This helps future readers understand the judgment lens used.

### 4. Active domain(s)
Record the active technical domains.

Examples:
- java
- spring
- redis
- mysql
- testing

### 5. Evidence summary
List the strongest supporting inputs.

Examples:
- reviewed service implementation
- transaction annotation behavior
- Redis invalidation path
- missing regression test
- failing CI trace
- query shape and index assumptions

Keep this section concise but concrete.

### 6. Findings / conclusions
Summarize the main conclusions.

For each major point include:
- what was found
- why it matters
- confidence
- whether it is verified or inferred

### 7. Recommended actions
Provide prioritized next steps.

Good examples:
1. move cache invalidation to post-commit path
2. add regression test for stale-read scenario
3. audit alternate write paths for invalidation bypass

### 8. Verification status
State:
- what was verified
- what was not verified
- what confidence level is justified

### 9. Risks / open questions
Capture residual uncertainty and follow-up needs.

Examples:
- invocation path for transaction proxying not confirmed
- no runtime concurrency test harness available
- production TTL configuration not shown

### 10. Delivery note
Optional final section for communication guidance.

Examples:
- safe to proceed with local fix first
- broader refactor should wait for regression coverage
- diagnostic data needed before stronger conclusion

---

## Style Guidance

- concise but archival
- structured for future re-read
- avoid chat-style phrasing
- preserve assumptions and uncertainty
- keep action items prioritized

---

## Good Fit Examples

Use this report for:
- task handoff
- engineering notes
- design follow-up
- recorded review outcome
- implementation planning artifact

---

## Avoid

Avoid using this report for:
- trivial one-off conversational replies
- purely conceptual explanations unless they need to be stored
- highly formal incident reporting where incident-specific structure is needed

---

## Short Reminder

Task report means:
- what the task was
- what was reviewed/analyzed
- what was concluded
- what should happen next
- what remains uncertain
