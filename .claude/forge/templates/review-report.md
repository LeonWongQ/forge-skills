# Template: Review Report

## Purpose

Use this template when the primary task is review.

This template is designed for outputs that must communicate:
- findings
- severity or priority
- supporting evidence
- why the issue matters
- suggested remediation direction
- overall risk posture

It is appropriate for:
- code review
- config review
- architecture review
- test review
- change review
- focused risk review

---

## Output Structure

### 1. Findings
For each meaningful finding, use the following structure:

#### Finding title
A short, specific description.

#### Severity
Use a proportional severity or priority label:
- Critical
- High
- Medium
- Low

#### Evidence
Include the direct observation:
- code behavior
- config value
- test weakness
- framework interaction
- edge-case omission

#### Why it matters
Explain:
- failure mode
- impact
- affected conditions
- why this is risky or costly

#### Suggested direction
Provide:
- fix direction
- safer design approach
- validation note
- optional narrower alternative

#### Confidence
State:
- High
- Medium
- Low

Use lower confidence when context is incomplete.

If no actionable findings are supported, state that directly before any summary and identify residual test or context gaps.

### 2. Open questions or assumptions
List only unresolved context that materially affects a finding or its confidence.

### 3. Scope and summary
Briefly state what was reviewed and the overall risk posture after the findings.

### 4. Positives
Include notable strengths when relevant and useful.

Examples:
- good separation of responsibilities
- clear transaction demarcation
- strong test naming
- sensible fallback behavior

This keeps the report fair and useful.

### 5. Recommended next steps
Provide a prioritized action list.

Good forms:
1. fix high-severity correctness issue
2. add validation or regression test
3. consider structural cleanup after correctness is restored

---

## Severity Guidance

Severity should reflect:
- impact
- likelihood
- recoverability
- operational cost

Do not inflate maintainability concerns into correctness-level severity.

---

## Style Guidance

- findings should be prioritized
- avoid flooding the report with weak issues
- be direct and specific
- explain why each finding matters
- preserve evidence/uncertainty distinction

---

## Good Fit Examples

Use this template for:
- PR review
- service review
- cache design review
- test suite review
- migration review
- targeted framework risk review

---

## Avoid

Avoid using this template when the task is primarily:
- root cause investigation
- phased refactor design
- implementation planning
- conceptual explanation

Use the corresponding specialized template instead.

---

## Short Reminder

Review report means:
- prioritized findings first
- evidence + impact for each finding
- scope and summary as secondary context
- practical next steps
