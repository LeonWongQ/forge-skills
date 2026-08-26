---
name: test-strategy
description: >-
  Analyze existing test reports, execution results, and defect data to formulate
  testing strategy, design targeted test cases, define auto-assertion rules, and
  diagnose test gaps. Transforms test evidence into actionable testing decisions.
  Use when the user says: analyze test report, review test results, formulate
  test strategy, design test cases from report, what should we test next,
  test gap analysis, create test plan from results, auto-assertion strategy,
  test coverage review, improve test strategy, test optimization plan,
  based on this report, given these test results, from this defect data,
  分析测试报告, 制定测试策略, 根据测试结果制定用例, 测试缺口分析,
  自动化断言策略, 测试优化方案, 基于报告设计测试, 测试策略优化,
  从测试报告看应该加什么测试, 测试覆盖分析, 测试改进方案.
  For any test strategy, test case design, or test optimization driven by
  existing test reports and execution data.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
context: inherit
---

# Test Strategy

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Classify the task intent:
   - **Analyze test report → strategy & cases** → Strategy Design path (section 3)
   - **Review test execution results → gap analysis** → Gap Analysis path (section 4)
   - **Define auto-assertion strategy** → Assertion Strategy path (section 5)
   - **Diagnose test quality issues** → Diagnosis path (section 6)
   - **Ambiguous** → ask one clarifying question, then route
3. Identify input artifacts:
   - Test execution reports (pass/fail/blocked/skipped counts, defect lists)
   - Historical defect data (frequency, severity, root causes)
   - Code coverage reports
   - Existing test cases / test plans
   - CI pipeline results
4. Detect technical domains from the project under test:
   - Java/Spring → `.Codex/forge/domains/java.md`, `.Codex/forge/domains/spring.md`
   - Playwright/UI → `.Codex/forge/domains/playwright.md`
   - Database → `.Codex/forge/domains/mysql.md`
   - Cache → `.Codex/forge/domains/redis.md`
   - Always load `.Codex/forge/domains/testing.md`
   - If no clear domain signal, skip additional domains. Note which were checked.
5. Compose forge modules per section 2
6. Execute the selected path
7. Deliver structured output

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Kernel | `.Codex/forge/AGENTS.md` | Universal engineering principles |
| Autoload | `.Codex/forge/AUTOLOAD.md` | Selective activation policy |
| Behavior (primary) | `.Codex/forge/behaviors/review.md` | Evaluate test quality, coverage, risk |
| Behavior (secondary) | `.Codex/forge/behaviors/document.md` | Produce structured strategy and test cases |
| Domains | `.Codex/forge/domains/testing.md` | Test design: assertions, isolation, coverage, layers |
| | Detected from project | Technology-specific failure modes |
| Template | `.Codex/forge/templates/test-plan.md` | Structured test strategy and case output |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/review-checklist.md` | Review quality: evidence-based, actionable |
| | `.Codex/forge/checklists/test-plan-checklist.md` | Test plan completeness |
| | `.Codex/forge/checklists/verification-checklist.md` | Claims justified and bounded |
| | `.Codex/forge/checklists/delivery-checklist.md` | Output is usable |
| Workflow | `workflow.full_default` | discover → evidence → context → reasoning → planning → execution → verification → delivery |

---

## 3. Strategy Design Path

### 3.1 Input digestion

Extract structured data from the provided test report(s):

| Data point | Why it matters |
|-----------|---------------|
| Total / passed / failed / blocked / skipped | Execution completeness |
| Failures by module/feature | Hotspots — where bugs concentrate |
| Defect severity distribution | Risk profile — where damage concentrates |
| Defect root cause categories | Systemic weaknesses (logic, integration, data, timing) |
| Coverage gaps (untested modules/features) | Blind spots — what no test covers |
| Test execution time / flaky test rate | Process health — CI friction |
| Pass-rate trends over time | Quality trajectory — improving or degrading? |

Do not accept numbers at face value. Question:
- Are blocked/skipped tests hiding real gaps?
- Is "100% pass rate" because tests are weak, not because code is bug-free?
- Are flaky tests being retried away without root-cause fix?

### 3.2 Pattern extraction

Identify patterns from the data:

| Pattern | Signal | Strategy implication |
|---------|--------|---------------------|
| Failures cluster in module X | High-complexity or poorly-tested area | Increase coverage depth in module X |
| Defects are mostly integration issues | Unit tests miss contract violations | Add contract/integration tests at boundaries |
| UI tests fail more than API tests | UI tests are brittle or page is unstable | Audit locator/wait strategy; add API-level coverage |
| High flaky rate (>5%) | Timing, shared state, or env issues | Dedicated flakiness fix sprint before adding new tests |
| Low coverage in critical path | Risk exposure | Prioritize critical path test cases |
| Regressions in "fixed" areas | Tests don't actually catch the regression | Strengthen assertions; add negative test cases |
| Many P0/P1 defects in UAT | Shift-left: tests miss what users find | Add user-journey-based test scenarios |

### 3.3 Strategy formulation

Produce a concrete testing strategy with these sections:

#### 3.3.1 Risk-based priority matrix

```
High Risk + Low Coverage → IMMEDIATE action
High Risk + High Coverage → MONITOR and strengthen assertions
Low Risk + Low Coverage → SCHEDULE baseline coverage
Low Risk + High Coverage → MAINTAIN current level
```

#### 3.3.2 Test layer allocation

For each risk area, allocate tests to the right layer:

| Behavior | Unit Test | Integration Test | E2E/UI Test |
|----------|-----------|-----------------|-------------|
| Pure business logic | ✅ Primary | — | — |
| API contract / serialization | — | ✅ Primary | — |
| DB query / transaction | — | ✅ Primary | — |
| Critical user journey | — | — | ✅ Primary |
| Error handling / edge case | ✅ Primary | ✅ Confirm | — |
| UI rendering / interaction | — | — | ✅ Primary |

#### 3.3.3 Coverage target by priority

| Priority | Unit Coverage | Integration Coverage | E2E Coverage |
|----------|-------------|---------------------|--------------|
| P0 (critical path) | ≥90% | Mandatory | ≥1 happy path |
| P1 (important) | ≥80% | Key scenarios | — |
| P2 (nice-to-have) | ≥60% | — | — |

### 3.4 Test case design

For each identified gap or risk area, design concrete test cases:

```
### Test Case: <descriptive name>
- **Priority**: P0 / P1 / P2
- **Layer**: Unit / Integration / E2E
- **Target**: <module/feature/endpoint/page>
- **Scenario**: <precise description of what is tested>
- **Preconditions**: <required state, data, auth>
- **Input / Steps**: <concrete steps or input values>
- **Expected Outcome**: <exact expected behavior>
- **Auto-Assertion Rules**: <what specific assertions verify this>
- **Failure Signal**: <what a failure here means>
- **Traceability**: ← <report section, defect ID, or risk item that justifies this test>
```

**Test case design principles:**
- One behavior per test case (not multiple unrelated checks)
- Test case name describes scenario + expected outcome
- Assertions are specific enough that a failure immediately indicates what regressed
- Every test case traces back to a report finding, defect, or identified risk

---

## 4. Gap Analysis Path

When the task is specifically: "based on these results, what tests are missing?"

### 4.1 Coverage dimension analysis

Evaluate coverage across ALL dimensions, not just code line coverage:

| Dimension | Question | Red Flag |
|-----------|----------|----------|
| **Feature coverage** | Are all features/APIs/pages tested? | Feature released but no test exists |
| **Scenario coverage** | Happy path, alternative, error, edge case? | Only happy paths tested |
| **Data coverage** | Null, empty, boundary, large, special chars? | Only "normal" data tested |
| **User role coverage** | All permission levels tested? | Only admin role tested |
| **Environment coverage** | Cross-browser, viewport, locale? | Only Chrome/1920×1080 tested |
| **Integration coverage** | All external dependencies exercised? | Mock always returns success |
| **Negative coverage** | Are failure modes tested? | All tests expect success |
| **Regression coverage** | Do tests exist for previously fixed bugs? | Bug fixed → test → bug reappears |

### 4.2 Gap prioritization

```
Critical Gap (fix immediately):
  - Critical path has zero test coverage
  - Previously-fixed bug has no regression test
  - Error handling path completely untested

High Priority Gap (fix this sprint):
  - P0 feature has only happy path, no error/edge case
  - Integration boundary has no contract test
  - Permission-sensitive flow has no role-based test

Medium Priority Gap (schedule for next sprint):
  - P1 feature lacks negative test cases
  - Cross-browser coverage missing for key pages
  - Performance/degradation tests missing

Low Priority Gap (backlog):
  - P2 feature documentation tests
  - Visual regression snapshots
  - Accessibility testing
```

---

## 5. Auto-Assertion Strategy Path

When the task focuses on "what should be auto-asserted?"

### 5.1 Assertion taxonomy

| Assertion Type | What It Verifies | Example |
|---------------|-----------------|---------|
| **State assertion** | System state after action | `expect(order.status).toBe('CONFIRMED')` |
| **Value assertion** | Exact value correctness | `expect(response.total).toBe(149.99)` |
| **Presence assertion** | Something exists | `expect(page.getByText('Success')).toBeVisible()` |
| **Absence assertion** | Something does NOT exist | `expect(page.getByText('Error')).not.toBeVisible()` |
| **Contract assertion** | API response shape | `expect(response).toMatchSchema(OrderSchema)` |
| **Relationship assertion** | Data integrity across entities | `expect(order.items.length).toBe(request.itemCount)` |
| **Temporal assertion** | Timing/order of events | `expect(eventA.timestamp).toBeBefore(eventB.timestamp)` |
| **Side-effect assertion** | External system state | `expect(auditLog).toContainEqual({ action: 'CREATE' })` |

### 5.2 Assertion strength calibration

For each test scenario, calibrate to the STRONGEST assertion that is maintainable:

```
Level 0: No assertion → test is worthless (false confidence)
Level 1: assertNotNull / status 200 → too weak (misses real bugs)
Level 2: assert key value → minimum viable ✓
Level 3: assert complete response / state → good confidence ✓✓
Level 4: assert + contract/schema validation → strong confidence ✓✓✓
Level 5: assert + mutation test (break code → test fails) → verified ✓✓✓✓
```

**Target**: Level 2 minimum for all tests. Level 3 for P0. Level 4 for critical integration points.

### 5.3 Auto-assertion design rules

1. **Assert user-visible behavior**, not implementation internals
2. **One assertion focus per test** — if you need multiple, they should all relate to the same behavior
3. **Assertion message**: provide context for CI debugging (`expect(x).toBe(y, 'Order total mismatch after discount')`)
4. **Negative assertions**: verify not only what SHOULD happen, but what SHOULD NOT happen
5. **Soft assertions**: use `expect.soft()` when checking multiple independent things in one test

---

## 6. Diagnosis Path (Test Quality Issues)

When the user reports systemic test quality problems from their reports.

### 6.1 Common patterns and fixes

| Report Symptom | Likely Diagnosis | Fix Strategy |
|---------------|-----------------|--------------|
| High pass rate but bugs in production | Weak assertions (Level 0-1) | Strengthen to Level 3+; add negative tests |
| Many blocked/skipped tests each cycle | Environmental instability | Stabilize test environment; add mock/container strategy |
| Flaky rate >5% | Timing, shared state, or env issues | Dedicated flakiness triage; run-repeat 100× verification |
| Test suite time growing | Heavy integration/E2E tests | Push tests down the pyramid (E2E → integration → unit) |
| Tests break on unrelated changes | Brittle tests (implementation-coupled) | Decouple from implementation; test behavior not internals |
| Defects found in UAT not caught earlier | Test gap at lower layers | Shift-left: add unit + integration tests for UAT-found scenarios |
| Same bug class keeps appearing | Missing test pattern for that class | Create test template/helper for that bug class |

### 6.2 Test health metrics

Calculate and benchmark:
- **Flaky rate**: should be <2% (retries don't count as "fixed")
- **Execution time trend**: should be flat or decreasing (not growing with features)
- **Defect escape rate**: bugs found in production / total bugs found → should decrease
- **Test-to-code ratio**: meaningful test lines / implementation lines → context-dependent, but should grow with criticality

---

## 7. Output Structure

### Strategy + Test Cases Output
```
## 1. Input Summary
<digested data from provided reports: key metrics, patterns, hotspots>

## 2. Risk-Priority Matrix
<table: risk × coverage → action>

## 3. Testing Strategy
- Risk-based focus areas (ordered by priority)
- Test layer allocation (what to test at which level)
- Coverage targets by priority tier

## 4. Gap Analysis
<what is NOT tested that should be, ordered by criticality>

## 5. Designed Test Cases
### Test Case 1: <name>
- Priority / Layer / Target
- Scenario / Preconditions / Steps
- Expected Outcome
- Auto-Assertion Rules
- Traceability ← <report evidence>

### Test Case N: ...

## 6. Auto-Assertion Calibration
<assertion strength baseline and upgrade recommendations>

## 7. Implementation Roadmap
<phased rollout: immediate → this sprint → next sprint → backlog>

## 8. Risks and Open Questions
```

### Pure Gap Analysis Output
```
## 1. Coverage Assessment
<dimension-by-dimension analysis with red/amber/green per dimension>

## 2. Prioritized Gaps
<critical → high → medium → low, each with concrete test case stub>

## 3. Recommended Actions
<specific next steps with owners and timeline>
```

---

## 8. Global Guard

- [ ] Task intent classified (strategy / gap analysis / assertion strategy / diagnosis)
- [ ] Input data extracted with specific numbers, not vague summaries
- [ ] Patterns identified with concrete evidence from reports
- [ ] Every recommended test case traces back to report evidence
- [ ] Assertions are specific and calibrated (Level 2 minimum)
- [ ] Risks and unknowns disclosed (what the data does NOT tell us)
- [ ] **Default output**: display inline. Write to file only with user confirmation of path. Default path: `reports/test-strategy-<date>.md`.

---

## 9. Quick Reference

| Report Finding → | Strategy Action |
|-----------------|----------------|
| Feature X has zero tests | Add P0 happy path + P1 error case for X |
| Defects cluster in integration layer | Add contract tests at service boundaries |
| Flaky rate >5% | Freeze new tests; dedicate sprint to flakiness fix |
| Tests pass but UAT finds bugs | Strengthen assertions to Level 3+; add user-journey scenarios |
| Coverage gap in error handling | Add negative test cases for all P0/P1 features |
| Regressions not caught | Add regression test for every fixed bug; verify test fails before fix |
| Slow test suite | Push E2E tests down to integration; add test parallelization |
