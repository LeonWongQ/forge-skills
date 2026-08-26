# Domain: Testing

## 1. Activation

Load this domain when the task involves evaluating test quality, test coverage, test design, assertion strength, flakiness, or test maintainability.

**Auto-detect signals**: test files (`*Test.java`, `*Tests.java`, `*Spec.java`), `@Test` annotations, JUnit/TestNG/Mockito imports, assertions, test fixtures, test configuration files.

**Activation discipline**: This domain should activate ONLY when the task directly involves test code, test strategy, test quality assessment, or test design — not merely because a pack includes it. Loading testing domain for a pure code review, refactoring, or performance optimization that does not mention testing adds noise without value.

**Specific activation conditions**:
- Task explicitly mentions testing (test code, test strategy, test coverage, test quality, flakiness)
- Target artifact is a test file or test configuration
- Task involves designing, implementing, reviewing, or debugging tests
- Task output includes test plan, test cases, or test strategy sections

**Do NOT activate** when:
- Task is a pure code review of non-test code (testing domain adds no value to reviewing business logic)
- Task is a performance optimization with no test dimension (unless user asks about test validation)
- Task is a documentation request with no testing component

---

## 2. Review Checklist

When reviewing tests, verify each item.

### 2.1 Test Intent and Naming
- [ ] Test name describes the scenario and expected outcome (not just the method name)
- [ ] One behavior per test — not multiple unrelated assertions
- [ ] Test tests behavior (what the code does), not implementation (how it does it)
- [ ] Test would fail meaningfully if the behavior regressed
- [ ] Test passes for the right reason, not coincidentally

### 2.2 Determinism
- [ ] No dependence on execution order — test passes when run alone and in any order
- [ ] No dependence on system clock (no `Thread.sleep`, no `new Date()`, no `System.currentTimeMillis()` without control)
- [ ] No dependence on external services (network, file system, other processes) unless explicitly an integration test
- [ ] Random data: seeded and reproducible, or avoided entirely
- [ ] Shared state between tests is reset in `@BeforeEach`/`@AfterEach`

### 2.3 Assertion Quality
- [ ] Assertion is specific: what exact value/state is expected?
- [ ] Not just `assertNotNull` when deeper behavior matters
- [ ] Not just HTTP 200 when response body correctness matters
- [ ] Exception tests: verify exception type AND message where relevant
- [ ] Multiple assertions in one test: is failure localization clear?
- [ ] Assertion message: provides context for debugging when it fails

### 2.4 Coverage
- [ ] Happy path covered
- [ ] Edge cases covered (null, empty, boundary values, maximum/minimum)
- [ ] Failure paths covered (exceptions, error responses, timeouts)
- [ ] Concurrency scenarios covered if applicable
- [ ] Risky/complex logic has more tests than trivial code
- [ ] Regression tests exist for previously fixed bugs

### 2.5 Mocking and Isolation
- [ ] Mocks represent the real contract, not just the current implementation
- [ ] Not mocking internals (private methods, internal helper calls)
- [ ] Mock setup is minimal — only stubs needed for the specific scenario
- [ ] Real implementations used where mocking would hide bugs (value objects, simple services)
- [ ] Mock verification: `verify()` only on behavior-critical interactions, not every call

### 2.6 Test Data and Fixtures
- [ ] Test data is explicit and visible in the test (not hidden in setup files)
- [ ] Test data values are meaningful for the scenario (not "foo", "bar", 12345)
- [ ] Fixtures are reset between tests
- [ ] Large shared fixtures: is the coupling between tests acceptable?

### 2.7 Layer Appropriateness
- [ ] Unit test for pure logic, edge cases, fast feedback
- [ ] Integration test for framework behavior, DB interaction, serialization
- [ ] E2E test for critical user flows, not for exhaustive coverage
- [ ] Test is at the right layer — not an integration test where a unit test would suffice (or vice versa)

### 2.8 Maintainability
- [ ] Setup is proportional to the behavior under test (not 20 lines of setup for 1 assertion)
- [ ] Helper methods improve readability without hiding critical details
- [ ] Test would be understandable to a new team member without extensive explanation
- [ ] Test is not duplicated across multiple test classes without reason

---

## 3. Debug Heuristics

### Pattern: Flaky Test
- **Symptom**: Test passes sometimes, fails other times, no code change
- **Common causes (check in order)**:
  1. Timing assumption (`Thread.sleep`, fixed timeout, no `await().atMost()`)
  2. Order dependence (test B expects state from test A)
  3. Shared mutable state not reset
  4. External service instability (network, DB, third-party API)
  5. Random/uncontrolled data producing different results
  6. Concurrency race in the code under test
  7. Environment difference (timezone, locale, OS, available cores)
- **Diagnose**: Run test in loop 100 times. Run alone vs with suite. Check for time-dependent assertions. Check `@BeforeEach`/`@AfterEach` reset.
- **Fix**: Use `await()` with timeout for async; reset state properly; use test containers not shared DB; seed random generators

### Pattern: Test Passes But Should Fail
- **Symptom**: Test is green, but the behavior it claims to test is broken
- **Common causes**: No assertion (test just runs without checking), assertion too weak (`assertNotNull`), mock returns the expected value regardless of input, test data doesn't exercise the edge case
- **Diagnose**: Break the code intentionally — does the test fail? If not, the test is not protecting anything.
- **Fix**: Strengthen assertions to match the behavioral contract; verify with intentionally broken code

### Pattern: Slow Test Suite
- **Symptom**: Test execution time growing, developer friction increasing
- **Common causes**: Too many integration/E2E tests, `@SpringBootTest` loading full context unnecessarily, unoptimized DB setup per test class, no test parallelization
- **Diagnose**: Profile test execution — which tests are slowest? Are they at the right layer?
- **Fix**: Slice tests (`@WebMvcTest`, `@DataJpaTest` instead of `@SpringBootTest`); test parallelization; faster test data setup

---

## 4. Error Patterns

| Symptom | Meaning | Common Causes | Fix Direction |
|---------|---------|---------------|---------------|
| Test fails ONLY in CI | Environment-dependent behavior | Different OS, locale, timezone, available memory, timing | Make test environment-independent; use test containers |
| Test fails randomly | Flaky test | See debug pattern above | See debug pattern above |
| Test passes with broken code | Weak or missing assertions | No assertion, assertion too broad, mock hiding bug | Strengthen assertions; reduce mocking |
| Test fails with unclear message | Poor failure localization | Generic assertion without message, multiple assertions in one test | Add assertion messages; split into focused tests |
| Test setup takes too long | Heavy fixtures or full context | `@SpringBootTest` for simple unit behavior, large test data | Use sliced context; lighter fixtures |
| Test fails after unrelated change | Brittle test | Test coupled to implementation details, over-mocking | Test behavior not implementation; reduce mock specificity |

---

## 5. Refactor Guidelines

When refactoring tests, verify:
- [ ] Test still tests the same behavior after refactoring
- [ ] Test name still accurately describes the scenario
- [ ] Assertions not weakened during refactoring
- [ ] Setup changes don't accidentally share state between tests
- [ ] Extracted helper methods don't hide critical setup details
- [ ] Mock setup still represents real contract after code changes

---

## 6. Verification Rules

- [ ] Run-each-test-alone: every test passes when run individually
- [ ] Run-repeat: flaky-prone tests pass 10+ consecutive runs
- [ ] Mutation check (optional but high-confidence): intentionally break the code — does the test catch it?
- [ ] Assertion walkthrough: for each test, confirm "if this assertion fails, do I know exactly what regressed?"
- [ ] Coverage gap check: what risky behavior has NO test?
