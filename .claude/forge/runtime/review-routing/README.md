# Review Routing Asset Pack

A reusable asset pack for routing review-related requests to the correct execution path.

This pack is intended to ensure that review tasks are:
- recognized consistently
- routed to the correct skill or forge behavior
- supported by the right domain context
- delivered in a structured review format

It helps prevent review requests from falling back into unstructured free-form responses when a formal review path should be used.

---

## 1. Purpose

Review requests are often ambiguous.
Users may say:
- review
- 帮我 review 一下
- code review
- 帮我看下改动
- 审一下
- 评审一下

But these requests may refer to different targets:
- GitHub PR
- local diff / patch / working tree changes
- code snippet
- design document
- implementation plan
- test plan
- test report
- other artifacts

This pack defines how to:
- detect review intent
- classify review context
- route to the correct skill or forge behavior
- apply supporting checklist/domain/template rules
- enforce structured output

---

## 2. Contents

- `review-routing-spec.md`  
  Main routing specification for review-related requests.

- `review-routing-checklist.md`  
  Checklist used to validate whether routing and output structure are correct.

- `review-routing-examples.md`  
  Concrete routing examples, including correct routes and anti-examples.

- `review-routing-workflow.md`  
  Step-by-step workflow for classifying, routing, and delivering a review task.

---

## 3. When to Use

Use this pack when:
- a request contains review intent
- a system needs to choose between `/review`, `/code-review`, or forge review behavior
- a review-related routing failure is being analyzed
- routing rules for review tasks need to be standardized
- structured review delivery needs to be enforced

Typical usage scenarios:
- GitHub PR review
- local working diff review
- code snippet review
- test plan / test report review
- design / implementation plan review
- framework/domain-aware technical review

---

## 4. Key Problem This Pack Solves

Without explicit routing rules, review requests may:
- be answered directly in free-form style
- skip the correct skill
- skip forge behavior loading
- skip domain loading
- skip checklist/template constraints
- produce inconsistent depth and structure

This pack reduces those failures by making review routing explicit.

---

## 5. Recommended Usage Flow

1. Detect review intent
2. Classify review context
3. Decide whether the target is:
   - PR
   - local diff
   - artifact/document/snippet
   - ambiguous
4. Route to the best available executor:
   - `/review`
   - `/code-review`
   - forge review behavior
5. Load review checklist and relevant domains
6. Produce structured review output
7. Validate using `review-routing-checklist.md`

For detailed execution steps, refer to:
- `review-routing-workflow.md`

---

## 6. Routing Summary

### Preferred routing
- GitHub PR -> `/review`
- local diff / patch / working changes -> `/code-review`
- artifact / document / code snippet / plan / report -> forge review behavior
- ambiguous review request -> minimal clarification or forge fallback

### Important rule
Recognized review tasks should not go directly to unstructured free-form output.

---

## 7. Supporting Forge Modules

When forge review behavior is used, the recommended baseline modules are:

### Required baseline
- `behaviors/review.md`
- `checklists/review-checklist.md`

### Optional but recommended
- `checklists/general-quality.md`

### Domain modules by context
- Java -> `domains/java.md`
- Spring -> `domains/spring.md`
- Testing artifacts -> `domains/testing.md`
- Redis/cache -> `domains/redis.md`
- MySQL/data access -> `domains/mysql.md`

### Template
- `templates/review-report.md` if available

---

## 8. Output Expectations

Structured review output should normally include:
- finding
- severity
- evidence
- impact
- recommendation or direction
- confidence when required

Even for lightweight review requests, the response should retain review discipline.

---

## 9. Recommended Minimum Use

For a lightweight setup:
- `review-routing-spec.md`

For operational use:
- `review-routing-spec.md`
- `review-routing-checklist.md`

For team/process standardization:
- all files in this pack

---

## 10. Suggested Maintenance

Update this pack when:
- new review-related skills are introduced
- routing mistakes are observed
- forge review behavior changes
- domain coverage changes
- review template/checklist conventions change

Recommended maintenance actions:
- add new trigger phrases
- add new routing examples
- record anti-patterns
- align severity and confidence conventions

---

## 11. File List

- `README.md`
- `review-routing-spec.md`
- `review-routing-checklist.md`
- `review-routing-examples.md`
- `review-routing-workflow.md`

---

## 12. Summary

This asset pack provides a reusable and structured way to ensure that review requests are:
- detected correctly
- routed correctly
- analyzed with the right context
- delivered in a consistent and auditable format

It can be used as a standalone routing pack or integrated into a larger skill/forge execution system.
