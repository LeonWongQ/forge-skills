# Review Routing Spec

> **Review routing suite** — this spec is part of a five-document pack:
> - `README.md` — pack overview and routing summary
> - `review-routing-spec.md` (this file) — rules, priorities, output structure
> - `review-routing-checklist.md` — pre-delivery validation
> - `review-routing-examples.md` — concrete examples and anti-examples
> - `review-routing-workflow.md` — step-by-step execution workflow

## 1. Purpose

This document defines how review-related requests should be routed to the correct execution path.

Its goals are to:
- distinguish different kinds of review tasks
- select the correct skill or forge behavior
- ensure structured and consistent review output
- avoid fallback to unstructured free-form responses when a review workflow should be used

This spec applies to requests such as:
- review
- code review
- CR
- 帮我 review 一下
- 帮我看下改动
- 审一下
- 评审一下
- review this diff / PR / file / document / plan / report

---

## 2. Problem Statement

Review requests are often underspecified.
A user may only say "review" without clarifying:
- whether the target is a GitHub PR or a local diff
- whether the artifact is code, document, test plan, or report
- whether a skill should be used
- whether forge review behavior should be activated

Without explicit routing, the system may:
- answer directly in free-form style
- skip the correct skill
- skip forge behavior/domain/checklist/template loading
- produce inconsistent review quality and structure

This spec prevents that.

---

## 3. Routing Goals

When a request is identified as a review task, the system should:

1. classify the review target
2. determine the review context
3. select the highest-priority matching executor
4. activate supporting forge modules when appropriate
5. enforce structured review output

---

## 4. Review Task Detection

A request should be treated as a review task if it contains explicit or implicit review intent.

### 4.1 Explicit review triggers
Examples:
- review
- code review
- CR
- review this
- review this diff
- review this PR
- review this file
- 帮我 review 一下
- 帮我看下改动
- 帮我审一下
- 帮我评审一下
- 看看有没有问题
- 帮我检查一下

### 4.2 Implicit review triggers
Examples:
- this implementation looks risky?
- check this change
- see whether this patch is okay
- help evaluate this plan
- verify whether this design/report is sound

If the user is asking for evaluation, defect finding, risk identification, or quality judgment on an artifact, treat it as a review task.

---

## 5. Review Context Classification

Review requests must be classified by context before execution.

### 5.1 GitHub PR review
Indicators:
- PR URL
- references to GitHub pull request
- comments like "review this PR"

Route to:
- skill: `/review`

### 5.2 Local diff / working tree review
Indicators:
- git diff
- patch
- changed files
- local modifications
- working diff
- current changes
- branch changes

Route to:
- skill: `/code-review`

### 5.3 Artifact review
Indicators:
- file content
- code snippet
- design doc
- test plan
- test report
- implementation plan
- architecture note
- review this document/report/plan

Route to:
- forge review behavior

### 5.4 Generic review with unclear target
Indicators:
- only "review"
- only "帮我 review 一下"
- no explicit PR/diff/artifact type

Route to:
- ask one clarifying question if required
- otherwise default to forge review behavior as fallback

---

## 6. Routing Priority

Review routing should follow this priority order:

### Priority 1: Explicit skill match
If the request clearly matches a specific skill context, use the skill.

Examples:
- GitHub PR -> `/review`
- local diff / patch / working tree -> `/code-review`

### Priority 2: Forge review behavior
If the request is a review task but does not clearly match a skill-specific context, activate forge review behavior.

Required baseline:
- `behaviors/review.md`
- `checklists/review-checklist.md`
- appropriate review template if available

### Priority 3: Clarification
If target or context is too ambiguous to execute safely, ask a minimal clarifying question.

Examples:
- "Do you want a PR review, local diff review, or document review?"
- "What should be reviewed: code, plan, report, or another artifact?"

### Priority 4: Free-form fallback
Only use unstructured free-form response when:
- the request is not actually a review task
- or no skill/forge review path is applicable
- or the user explicitly asks for an informal quick opinion

Free-form fallback should not be the default for recognized review tasks.

---

## 7. Forge Module Activation Rules

When forge review behavior is selected, activate modules as follows.

### 7.1 Required baseline modules
Always load:
- `behaviors/review.md`
- `checklists/review-checklist.md`

### 7.2 Template selection
Use a review-oriented template when available, such as:
- `templates/review-report.md`

If no dedicated review template exists, use the closest structured evaluation template.

### 7.3 Domain selection
Load domains based on artifact type, language, or framework.

Examples:
- Java code -> `domains/java.md`
- Spring service/controller/config -> `domains/spring.md`
- Testing artifacts -> `domains/testing.md`
- Redis usage -> `domains/redis.md`
- MySQL/SQL/data access -> `domains/mysql.md`

If multiple domains apply, load all relevant ones with one primary domain.

### 7.4 General quality baseline
When applicable, also load:
- `checklists/general-quality.md`

This is especially useful for:
- actionability
- fact vs assumption separation
- completeness
- clarity

---

## 8. Skill vs Forge Selection Rules

### Use skill `/review` when:
- target is a GitHub PR
- review is tied to PR conventions and PR review workflow

### Use skill `/code-review` when:
- target is a local diff
- review is tied to current working changes or patch-based analysis

### Use forge review behavior when:
- target is a document, plan, report, design, artifact, or code snippet
- task requires domain-aware structured analysis
- no exact skill match exists
- review should follow framework standards

### Use both skill + forge structure when possible
If a skill is chosen and forge structure is available, the preferred pattern is:
- skill provides execution mode/context
- forge provides structure/domain/checklist/template

This gives the most consistent result.

---

## 9. Output Structure Requirements

All structured review outputs should include the following elements.

### 9.1 Minimum required fields
- Finding
- Severity
- Evidence
- Impact
- Recommendation or Direction
- Confidence

### 9.2 Optional but recommended fields
- Scope reviewed
- Assumptions
- Open questions
- Validation suggestions
- Affected modules/files
- Risk summary

### 9.3 Severity levels
Suggested severity levels:
- Critical
- High
- Medium
- Low
- Info

If the repository already defines severity standards, follow repository standards.

### 9.4 Confidence levels
Suggested confidence values:
- High
- Medium
- Low

Confidence should reflect evidence strength, context completeness, and certainty of the conclusion.

---

## 10. Output Guard Rules

Before finalizing a review response, perform a lightweight guard check.

### 10.1 Guard questions
- Is this a review task?
- Was the correct skill or forge behavior selected?
- Does the output contain findings?
- Does each finding include evidence?
- Is severity stated?
- Is impact explained?
- Is recommendation actionable?
- Is confidence indicated when required?

### 10.2 Guard failure handling
If the answer is missing required review structure:
- reformat before final output
- do not emit an informal free-form review as final response unless explicitly requested

---

## 11. Clarification Rules

Ask a clarifying question only when needed.

### Clarification is required when:
- the target artifact is unknown
- the context is ambiguous between PR and local diff
- the requested depth is unclear and affects execution path
- there is not enough material to review meaningfully

### Clarification should be minimal
Prefer one concise question over multiple questions.

Good examples:
- "Do you want a PR review or a local diff review?"
- "What should be reviewed: code, plan, or report?"

Bad examples:
- long multi-part interviews before any progress

---

## 12. Fallback Rules

If no exact route is available:

1. prefer forge review behavior over free-form output
2. apply a general review structure
3. state assumptions clearly
4. note limitations
5. request missing context only if necessary

Fallback should still preserve review discipline.

---

## 13. Examples

### Example A: GitHub PR
User:
- "Review this PR: https://github.com/.../pull/123"

Route:
- skill `/review`

Optional forge support:
- `behaviors/review.md`
- relevant domains
- `review-checklist.md`

### Example B: Local diff
User:
- "帮我 review 一下当前改动"

Context:
- working tree / local diff

Route:
- skill `/code-review`

Optional forge support:
- `behaviors/review.md`
- language/framework domains
- `review-checklist.md`

### Example C: Test plan review
User:
- "帮我 review 下这个 test-plan"

Route:
- forge review behavior

Modules:
- `behaviors/review.md`
- `domains/testing.md`
- `review-checklist.md`
- `templates/review-report.md`

### Example D: Spring service change review
User:
- "review 这个 service 改动"

Context:
- Java/Spring code artifact

Route:
- local diff -> `/code-review`
- or forge review behavior if artifact is pasted directly

Domains:
- `domains/java.md`
- `domains/spring.md`

### Example E: Ambiguous review request
User:
- "review 一下"

Route:
- ask one clarification if no artifact/context is present
- otherwise default to forge review behavior based on available material

---

## 14. Failure Modes to Avoid

Avoid the following behaviors:

- responding in free-form style immediately after seeing the word "review"
- treating all review requests as the same kind of review
- skipping context classification
- skipping domain loading for technical artifacts
- skipping review checklist
- producing recommendations without evidence
- producing findings without severity/impact
- giving implementation advice when the task is specifically review-only unless requested

---

## 15. Recommended Execution Pattern

The recommended execution chain is:

1. detect review intent
2. classify context
3. choose skill if explicit match exists
4. otherwise activate forge review behavior
5. load relevant domain(s)
6. load review checklist
7. select review template
8. analyze artifact
9. perform output guard
10. deliver structured review

---

## 16. Operational Summary

### Default rule
Recognized review tasks must not go directly to unstructured free-form output.

### Routing rule
- PR -> `/review`
- local diff -> `/code-review`
- artifact/doc/plan/report/snippet -> forge review behavior
- ambiguous -> clarify minimally or forge fallback

### Quality rule
Structured review output must include:
- finding
- severity
- evidence
- impact
- recommendation/direction
- confidence

---

## 17. Maintenance Notes

This spec should be updated when:
- new review-related skills are added
- forge review behavior changes
- new domain modules are added
- repository review template/checklist changes
- routing failures are observed in practice

Recommended maintenance actions:
- review false-routing cases
- add new trigger phrases
- update examples
- align severity/confidence conventions with actual usage
