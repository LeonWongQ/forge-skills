# Review Output Guard (condensed from review-routing-checklist.md)

Quick validation before delivering any review response.

## Context Check
- [ ] What is being reviewed? (PR / local diff / code snippet / document / plan / report)
- [ ] Was the review context classified before analysis began?
- [ ] If target was ambiguous, was a clarification asked?
- [ ] Explicit artifact scope was not expanded without evidence of a relevant dependency

## Finding Quality (per finding)
- [ ] Finding is specific (not vague)
- [ ] Severity is stated (Critical / High / Medium / Low)
- [ ] Evidence is cited (code reference, line number, observable behavior)
- [ ] Impact is explained (concrete failure scenario)
- [ ] Direction is actionable (not just "fix this")
- [ ] Confidence is stated (High / Medium / Low)

## Prioritization
- [ ] Correctness issues listed before style issues
- [ ] Severity is proportional to impact + likelihood
- [ ] Weak or speculative concerns marked with lower confidence

## Completeness
- [ ] Edge cases considered
- [ ] Failure paths considered
- [ ] Domain-specific checks applied (Spring: proxy, transaction, bean scope; Java: null, concurrency; etc.)
- [ ] What is acceptable as-is is acknowledged (not every line needs a finding)
- [ ] Focused review used targeted checks and did not run an unrelated full test suite

## Anti-Patterns to Catch
- [ ] No free-form opinion without structure
- [ ] No "could be cleaner" without specifics
- [ ] No severity inflation (calling moderate issues "critical")
- [ ] No evidence-light claims
- [ ] No implementation advice mixed into review unless requested
