# Template: Debug Report

## Purpose

Use this template when the primary task is debugging, investigation, or root-cause analysis.

This template is designed for outputs that must communicate:
- symptom
- observed evidence
- ranked hypotheses
- root-cause status, including "not established" when evidence is incomplete
- corrective options only when requested
- a falsifiable diagnostic or validation path
- open uncertainty

It is appropriate for:
- production issue investigation
- test failure diagnosis
- framework behavior diagnosis
- integration failure analysis
- intermittent issue analysis

---

## Output Structure

### 1. Symptom summary
State:
- what is failing
- expected vs actual behavior
- conditions if known
- whether failure is deterministic or intermittent

Example:
"The Playwright test intermittently times out in CI while waiting for the modal to become visible. The same test usually passes locally."

### 2. Key evidence
List the strongest observed facts.

Examples:
- exact code behavior
- stack trace point
- timing pattern
- config difference
- weak locator
- transaction call path
- missing invalidation on one write path

Keep evidence separate from interpretation.

### 3. Ranked hypotheses
List likely explanations in descending order.

For each hypothesis include:
- explanation
- supporting evidence
- contradictory or missing evidence
- confidence / likelihood

This section is especially valuable when certainty is incomplete.

### 4. Root cause status
State whether root cause is established, not established, or only a leading candidate. Explain why the current status is justified over alternatives.

Include:
- trigger, causal mechanism, and enabling condition when established
- confidence, missing evidence, and a falsifier when incomplete
- important assumptions, if any

### 5. Fix options (only when requested)
Provide corrective directions only when the user requests a fix or remediation options.

For each option include:
- what to change
- why it should help
- tradeoffs
- whether it fixes root cause or only mitigates symptom

### 6. Next diagnostic step or verification plan
State the smallest check that can confirm or falsify the diagnosis. When a fix was requested, also state how to verify it.

Examples:
- reproduce with targeted logs
- rerun flaky scenario repeatedly
- verify proxy crossing
- add regression test
- inspect query plan under representative data

### 7. Open questions
List unresolved items that materially affect confidence.

Examples:
- missing environment-specific config
- unconfirmed transaction invocation path
- no runtime reproduction harness
- no production metrics available

---

## Style Guidance

- distinguish symptom from cause
- keep hypotheses explicit
- avoid premature closure
- make confidence visible
- include validation path

---

## Good Fit Examples

Use this template for:
- "why is this failing?"
- "find the root cause"
- flaky test analysis
- transaction issue diagnosis
- cache inconsistency investigation
- performance issue investigation with uncertain cause

---

## Avoid

Avoid using this template when the task is primarily:
- broad review
- structural refactor planning
- direct implementation planning
- concept explanation

---

## Short Reminder

Debug report means:
- define the symptom
- show the evidence
- rank hypotheses
- state root-cause status without forcing certainty
- end with a falsifiable next check or requested-fix validation
