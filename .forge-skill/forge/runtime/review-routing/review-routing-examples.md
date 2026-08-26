# Review Routing Examples

> **Review routing suite** — this examples doc is part of a five-document pack:
> - `README.md` — pack overview and routing summary
> - `review-routing-spec.md` — rules, priorities, output structure
> - `review-routing-checklist.md` — pre-delivery validation
> - `review-routing-examples.md` (this file) — concrete examples and anti-examples
> - `review-routing-workflow.md` — step-by-step execution workflow

## 1. Purpose

This document provides concrete routing examples for review-related requests.

It shows:
- how to classify review requests
- which skill or forge path should be selected
- which supporting modules should be loaded
- what kind of output structure is expected

These examples are intended to reduce ambiguity and improve routing consistency.

---

## 2. Example Format

Each example includes:
- User Request
- Context
- Expected Route
- Supporting Forge Modules
- Notes

---

## 3. Examples

### Example 1: GitHub PR review

**User Request**  
Review this PR: https://github.com/org/repo/pull/123

**Context**  
- explicit GitHub PR
- review target is a pull request

**Expected Route**  
- skill: `/review`

**Supporting Forge Modules**  
- `behaviors/review.md`
- `checklists/review-checklist.md`
- domain modules based on changed files

**Notes**  
This is the clearest case for PR review skill.  
Do not route this to `/code-review` unless the PR context is unavailable and only a raw diff is being reviewed.

---

### Example 2: Local working diff review

**User Request**  
帮我 review 一下当前改动

**Context**  
- current local changes
- working diff / unstaged or staged modifications
- not a GitHub PR

**Expected Route**  
- skill: `/code-review`

**Supporting Forge Modules**  
- `behaviors/review.md`
- `checklists/review-checklist.md`
- domain modules inferred from changed files

**Notes**  
This is the canonical case for local diff review.  
If code is Java/Spring, load `domains/java.md` and `domains/spring.md`.

---

### Example 3: Review a pasted Java class

**User Request**  
帮我 review 一下这个 service 实现

**Context**  
- pasted code artifact
- not clearly a PR
- not necessarily a git diff
- explicit technical code review request

**Expected Route**  
- forge review behavior
- optionally `/code-review` only if explicitly treated as local diff

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/java.md`
- `domains/spring.md` if relevant
- `checklists/review-checklist.md`
- `templates/review-report.md` if used

**Notes**  
Artifact-based review should prefer forge review behavior unless there is a stronger skill-specific context.

---

### Example 4: Review a test plan

**User Request**  
帮我 review 下这个 test-plan

**Context**  
- artifact is a testing document
- not a code diff
- document review

**Expected Route**  
- forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/testing.md`
- `checklists/review-checklist.md`
- `templates/review-report.md`

**Notes**  
Do not route this to code-review skill.  
This is a structured artifact review, not source code review.

---

### Example 5: Review a test report

**User Request**  
帮我看下这个 test-report 有没有问题

**Context**  
- artifact is a test report
- evaluation of completeness, clarity, risk communication

**Expected Route**  
- forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/testing.md`
- `checklists/review-checklist.md`
- optionally `checklists/general-quality.md`

**Notes**  
The review should focus on:
- coverage summary
- defect summary
- risk transparency
- conclusion clarity

---

### Example 6: Review implementation plan

**User Request**  
review 一下这个 implementation plan

**Context**  
- planning document review
- likely needs completeness and risk review

**Expected Route**  
- forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- relevant domain module if technical plan is domain-specific
- `checklists/review-checklist.md`
- `checklists/general-quality.md`

**Notes**  
The review should check:
- assumptions
- risks
- validation plan
- sequencing
- feasibility

---

### Example 7: Review Spring service change

**User Request**  
review 这个 Spring service 改动

**Context**  
- technical code review
- Spring service artifact or local diff
- Java/Spring domain clearly relevant

**Expected Route**  
- local diff: `/code-review`
- pasted artifact: forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/java.md`
- `domains/spring.md`
- `checklists/review-checklist.md`

**Notes**  
This route should trigger checks such as:
- dependency injection correctness
- bean availability
- transaction boundaries
- interface/implementation consistency
- exception path analysis

---

### Example 8: Review SQL/data access change

**User Request**  
帮我 review 下这个 DAO / SQL 改动

**Context**  
- data access artifact
- likely code or query review

**Expected Route**  
- local diff: `/code-review`
- pasted query/artifact: forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/java.md` if code layer involved
- `domains/mysql.md` if SQL/database relevant
- `checklists/review-checklist.md`

**Notes**  
Review should cover:
- query correctness
- index/scan risk awareness
- null handling
- transaction/data consistency

---

### Example 9: Review Redis/cache logic

**User Request**  
帮我 review 一下这段缓存逻辑

**Context**  
- cache-related technical artifact
- may involve code snippet or diff

**Expected Route**  
- local diff: `/code-review`
- pasted artifact: forge review behavior

**Supporting Forge Modules**  
- `behaviors/review.md`
- `domains/redis.md`
- `domains/java.md` if implementation language is Java
- `checklists/review-checklist.md`

**Notes**  
Review should cover:
- cache consistency
- invalidation strategy
- stampede / penetration / breakdown concerns
- key naming and TTL logic

---

### Example 10: Ambiguous review request with no artifact

**User Request**  
review 一下

**Context**  
- review intent exists
- target unknown
- insufficient context

**Expected Route**  
- ask one clarification question

**Supporting Forge Modules**  
- none until target/context is clarified
- or forge review fallback only if artifact is already visible elsewhere in context

**Notes**  
A good clarification:
- "你要我 review PR、当前 diff，还是某个文档/代码片段？"

A bad response:
- giving generic review advice without knowing the target

---

### Example 11: Quick informal opinion explicitly requested

**User Request**  
不用太正式，快速帮我看下这个改动有没有大问题

**Context**  
- review task still exists
- user requests lightweight style

**Expected Route**  
- still route as review
- local diff -> `/code-review`
- artifact -> forge review behavior

**Supporting Forge Modules**  
- lightweight use of review behavior/checklist

**Notes**  
Even if the tone is lighter, do not abandon review discipline completely.  
At minimum, still provide:
- issue
- impact
- recommendation

---

### Example 12: Mixed request - implement + review

**User Request**  
先帮我改一下，再顺便 review 一下实现是否合理

**Context**  
- mixed task
- implementation + review
- review is secondary but explicit

**Expected Route**  
- split task phases
- implementation route first
- then review route on resulting artifact/diff

**Supporting Forge Modules**  
- implementation-related modules first
- then `behaviors/review.md`
- review checklist and relevant domain modules

**Notes**  
Do not merge implementation and review into one unstructured stream.  
Treat review as a distinct phase.

---

## 4. Anti-Examples

### Anti-Example 1: Free-form answer after seeing "review"

**User Request**  
帮我 review 一下当前改动

**Wrong Behavior**  
- immediately writes a casual opinion
- no context classification
- no skill selection
- no structured findings

**Why Wrong**  
This bypasses both `/code-review` and forge review behavior.

---

### Anti-Example 2: Wrong skill for local diff

**User Request**  
帮我 review 一下当前分支改动

**Wrong Behavior**  
- routes to `/review`

**Why Wrong**  
This is not necessarily a GitHub PR.  
It should normally route to `/code-review`.

---

### Anti-Example 3: No domain loading for Spring review

**User Request**  
review 这个 Spring service 变更

**Wrong Behavior**  
- generic code comments only
- no Spring-specific checks

**Why Wrong**  
The system should load `domains/spring.md` and examine framework-specific risks.

---

### Anti-Example 4: Review without evidence

**User Request**  
review 这个实现

**Wrong Behavior**  
- says "this may have issues"
- no evidence
- no severity
- no impact

**Why Wrong**  
This is not a structured review.  
It is only a vague opinion.

---

## 5. Routing Decision Summary

### PR
- use `/review`

### Local diff / patch / working changes
- use `/code-review`

### Code snippet / file / plan / report / design doc
- use forge review behavior

### Ambiguous request
- ask minimal clarification
- or fallback to forge review if context is sufficiently available

---

## 6. Output Reminder

No matter which route is used, a structured review should normally include:
- finding
- severity
- evidence
- impact
- recommendation/direction
- confidence when applicable
