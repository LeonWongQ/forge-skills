# Review Routing Workflow

> **Review routing suite** — this workflow is part of a five-document pack:
> - `README.md` — pack overview and routing summary
> - `review-routing-spec.md` — rules, priorities, output structure
> - `review-routing-checklist.md` — pre-delivery validation
> - `review-routing-examples.md` — concrete examples and anti-examples
> - `review-routing-workflow.md` (this file) — step-by-step execution workflow

## 1. Purpose

This workflow defines how to process a review-related request from initial intent detection to final structured delivery.

It is intended to ensure that review tasks:
- do not bypass skill/forge routing
- use the correct review path
- activate the right supporting modules
- produce structured and evidence-based output

---

## 2. Inputs

Typical inputs include:
- user request containing review intent
- PR URL
- local diff / patch / changed files
- pasted code snippet
- design document
- implementation plan
- test plan / test report
- surrounding conversation context
- repository/runtime routing rules

---

## 3. Workflow Overview

The workflow has six main phases:

1. detect review intent
2. classify review context
3. choose execution route
4. activate supporting modules
5. perform review
6. validate final output

---

## 4. Workflow Steps

### Step 1: Detect review intent
Actions:
- read the request for explicit review trigger words
- identify implicit requests for evaluation, defect finding, or quality judgment
- confirm whether the task should be treated as review

Examples of triggers:
- review
- code review
- CR
- 帮我 review 一下
- 帮我看下改动
- 审一下
- 评审一下

Outputs:
- review task detected: yes/no

Decision:
- if not a review task, exit this workflow
- if yes, continue

---

### Step 2: Classify review context
Actions:
- identify what is being reviewed
- determine whether the target is:
  - GitHub PR
  - local diff / patch / working changes
  - code snippet or file content
  - document / plan / report
  - ambiguous/unknown

Context signals:
- PR URL -> PR review
- git diff / local changes -> local diff review
- pasted content -> artifact review
- plan/report/doc keywords -> document review

Outputs:
- classified review context

Decision:
- if context is unclear and routing would be unsafe, ask one minimal clarification question
- otherwise continue

---

### Step 3: Choose execution route
Actions:
- apply routing priority
- select the best matching executor

Routing priority:
1. explicit skill match
2. forge review behavior
3. clarification
4. free-form fallback only as last resort

Selection rules:
- PR -> `/review`
- local diff -> `/code-review`
- artifact/doc/snippet/plan/report -> forge review behavior
- ambiguous -> clarify minimally or use forge fallback if enough context exists

Outputs:
- selected route

Decision:
- if skill is selected, continue with skill-aware review
- if forge is selected, continue with forge module activation

---

### Step 4: Activate supporting modules
Actions:
- load review baseline modules
- load appropriate domains
- select a review template if available
- load quality checklist(s)

Baseline modules:
- `behaviors/review.md`
- `checklists/review-checklist.md`

Optional quality support:
- `checklists/general-quality.md`

Domain selection examples:
- Java -> `domains/java.md`
- Spring -> `domains/spring.md`
- Testing -> `domains/testing.md`
- Redis -> `domains/redis.md`
- MySQL -> `domains/mysql.md`

Template selection:
- `templates/review-report.md` if available

Outputs:
- active review support stack

Decision:
- if no domain applies, continue with general review baseline
- if multiple domains apply, load all relevant domains

---

### Step 5: Perform review
Actions:
- analyze the target artifact or change set
- identify issues, risks, inconsistencies, or gaps
- distinguish facts from assumptions
- record evidence for each finding
- assess impact and severity
- propose actionable recommendations

Expected review elements:
- finding
- severity
- evidence
- impact
- recommendation/direction
- confidence when applicable

Outputs:
- draft structured review

Decision:
- if no issues are found, still provide explicit review conclusion
- if evidence is weak, lower confidence and state assumptions

---

### Step 6: Validate final output
Actions:
- perform output guard check
- confirm structured review requirements are met
- ensure the response is not an unstructured free-form opinion
- confirm the chosen route still matches the actual target/context

Validation questions:
- is this clearly a review response?
- is the route correct?
- are findings structured?
- is evidence included?
- is severity stated?
- is impact explained?
- is recommendation actionable?

Outputs:
- final review response

Decision:
- if structure is missing, reformat before delivery
- if routing was wrong, reroute or clarify before delivery

---

## 5. Output Requirements

The final review output should generally contain:
- scope or target reviewed
- one or more findings if applicable
- severity
- evidence
- impact
- recommendation/direction
- confidence when relevant

For lightweight review:
- some sections may be shorter
- but review discipline should remain

---

## 6. Clarification Rule

Ask a clarification question only when it materially affects routing or review safety.

Good clarification:
- "Do you want a PR review or a local diff review?"
- "What should be reviewed: code, plan, or report?"

Bad clarification:
- multiple unnecessary questions before any progress
- asking for clarification when the context is already obvious

---

## 7. Fallback Rule

If no exact route is available:
1. prefer forge review behavior
2. apply structured review format
3. state assumptions
4. state limitations
5. avoid informal free-form output unless explicitly requested

---

## 8. Failure Modes

This workflow should prevent the following failures:
- direct free-form response after seeing "review"
- wrong skill chosen for the actual context
- missing forge review fallback
- missing domain activation
- findings without evidence
- findings without severity/impact
- vague opinion instead of structured review

---

## 9. Recommended Operational Pattern

Recommended execution chain:

1. detect review intent
2. classify context
3. choose route
4. activate baseline review modules
5. load relevant domains
6. perform review
7. validate output
8. deliver structured result

---

## 10. Exit Condition

The workflow is complete when:
- the request has been correctly identified as a review task
- the route has been correctly selected
- required supporting modules have been activated
- the review output is structured
- the result is suitable for audit, reuse, and follow-up action
