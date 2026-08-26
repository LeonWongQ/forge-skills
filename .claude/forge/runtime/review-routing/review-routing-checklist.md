# Review Routing Checklist

> **Review routing suite** — this checklist is part of a five-document pack:
> - `README.md` — pack overview and routing summary
> - `review-routing-spec.md` — rules, priorities, output structure
> - `review-routing-checklist.md` (this file) — pre-delivery validation
> - `review-routing-examples.md` — concrete examples and anti-examples
> - `review-routing-workflow.md` — step-by-step execution workflow

## 1. Purpose

This checklist is used to verify whether a review-related request has been routed correctly and whether the final review output follows the expected structure.

It is intended to prevent:
- incorrect skill selection
- missing forge behavior activation
- missing domain loading
- unstructured free-form review output
- incomplete review findings

Use this checklist:
- before delivering a review response
- when debugging routing failures
- when validating review workflow changes

---

## 2. Review Intent Detection

- [ ] Did the request explicitly ask for review, code review, CR, 审查, 评审, or similar?
- [ ] If not explicit, did the request still imply evaluation, defect finding, risk assessment, or quality judgment?
- [ ] Was the task correctly recognized as a review task rather than implementation/debug/documentation?

If the answer is no, routing may already be wrong.

---

## 3. Context Classification

- [ ] Was the review context classified before execution?
- [ ] Is the target a GitHub PR?
- [ ] Is the target a local diff / patch / working tree change?
- [ ] Is the target an artifact such as code snippet, file content, design doc, plan, or report?
- [ ] If the target was ambiguous, was a minimal clarification question asked?
- [ ] If no clarification was asked, was there enough context to select a safe default route?

---

## 4. Skill Selection

- [ ] If the target was a GitHub PR, was `/review` selected?
- [ ] If the target was a local diff / patch / working change, was `/code-review` selected?
- [ ] Was free-form response avoided when a skill match clearly existed?
- [ ] If a skill was selected, was the selected skill appropriate for the actual review target?

---

## 5. Forge Activation

- [ ] If no exact skill match existed, was forge review behavior used?
- [ ] Was `behaviors/review.md` activated?
- [ ] Was `checklists/review-checklist.md` activated?
- [ ] Was a review-oriented template selected when applicable?
- [ ] Was forge used as fallback instead of jumping directly to free-form output?

---

## 6. Domain Loading

- [ ] Was the primary technical or content domain identified?
- [ ] For Java code, was `domains/java.md` considered?
- [ ] For Spring code, was `domains/spring.md` considered?
- [ ] For testing artifacts, was `domains/testing.md` considered?
- [ ] For data access or database-related artifacts, was `domains/mysql.md` considered if applicable?
- [ ] For cache or Redis-related artifacts, was `domains/redis.md` considered if applicable?
- [ ] If multiple domains were relevant, were they loaded together?
- [ ] Was domain loading skipped without justification?

---

## 7. Output Structure

- [ ] Does the final review contain at least one clear finding when issues exist?
- [ ] Does each finding include a severity level?
- [ ] Does each finding include supporting evidence?
- [ ] Does each finding explain impact?
- [ ] Does each finding include a recommendation or direction?
- [ ] Is confidence stated when required by the review standard?
- [ ] If no issues were found, is the review still structured and explicit rather than vague?

---

## 8. Quality Guard

- [ ] Are facts clearly separated from assumptions?
- [ ] Are speculative concerns marked with lower confidence or explicit uncertainty?
- [ ] Are recommendations actionable?
- [ ] Are findings traceable to code, artifact content, file, behavior, or requirement?
- [ ] Was output format checked before final delivery?
- [ ] Was an unstructured free-form answer avoided for a recognized review task?

---

## 9. Clarification Handling

- [ ] Was clarification asked only when necessary?
- [ ] Was the clarification concise?
- [ ] Did the clarification unblock routing rather than create unnecessary delay?
- [ ] If no clarification was asked, was the chosen route still defensible based on available context?

---

## 10. Fallback Handling

- [ ] If no exact route existed, was forge review behavior used as the default fallback?
- [ ] If the response had to be lightweight, did it still preserve review discipline?
- [ ] Were assumptions and limitations clearly stated in fallback mode?
- [ ] Was free-form output used only as a last resort?

---

## 11. Final Validation Questions

Before finalizing a review response, confirm:

- [ ] Do I know what is being reviewed?
- [ ] Do I know whether this is PR review, local diff review, or artifact review?
- [ ] Did I route to the best available skill or forge path?
- [ ] Did I load the right technical/content domain?
- [ ] Does my output look like a real review rather than a general opinion?
- [ ] If someone audits this response later, will they see clear findings, evidence, and reasoning?

If any answer is no, the routing or output should be corrected before delivery.

---

## 12. Common Failure Patterns

Watch for these failure patterns:

- [ ] Saw the word "review" and responded immediately without classification
- [ ] Used `/review` for a local diff when `/code-review` was more appropriate
- [ ] Missed forge review fallback when no exact skill matched
- [ ] Skipped domain loading for technical artifacts
- [ ] Produced findings without severity or evidence
- [ ] Produced advice without showing what issue triggered it
- [ ] Used a casual opinion style instead of structured review format

Any checked item here indicates a routing or execution quality problem.

---

## 13. Summary Rule

A recognized review task is complete only when:
- the route is correct
- the right skill or forge behavior is used
- the right domain context is loaded
- the output is structured and evidence-based
