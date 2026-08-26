# Domain: Playwright

## 1. Activation

Load this domain when the task involves Playwright E2E tests, browser automation, UI test flakiness, locator strategy, or CI-specific browser failures.

**Auto-detect signals**: `@playwright/test`, `page.locator(`, `page.goto(`, `page.click(`, `expect(`, `browser`, `chromium`/`firefox`/`webkit`, Playwright config files, trace/screenshot references, CI-only UI failures.

---

## 2. Review Checklist

When reviewing Playwright tests, verify each item.

### 2.1 Locator Quality
- [ ] Locators use semantic roles (`getByRole`), text content (`getByText`), labels (`getByLabel`), or test IDs (`getByTestId`) — not CSS classes or DOM structure
- [ ] No `nth-child`, `xpath`, or deeply nested CSS selectors
- [ ] Each locator resolves to exactly one element on the page (or the test handles multiple matches explicitly)
- [ ] Locator survives minor UI changes (text change, layout restructure, CSS refactor)
- [ ] Visible text locators use the exact user-facing string

### 2.2 Wait Strategy
- [ ] No `waitForTimeout` / `page.waitForTimeout()` with fixed milliseconds
- [ ] No `setTimeout` or manual `sleep` calls
- [ ] All waits are condition-based: `waitForSelector`, `waitForResponse`, `waitForLoadState`, `waitForURL`
- [ ] Auto-waiting built into Playwright actions is relied upon (not overridden with `{ wait: false }`)
- [ ] After navigation, page state is explicitly synchronized before assertions
- [ ] Debounced inputs: waited for debounce period before asserting

### 2.3 Test Isolation
- [ ] Each test creates its own data or uses isolated fixtures
- [ ] No shared mutable state between tests (global variables, shared browser context state)
- [ ] Test order independence: tests pass when run alone, in any order, and in parallel
- [ ] `beforeEach` properly resets all state
- [ ] No dependence on data created by another test

### 2.4 Assertion Quality
- [ ] Assertions verify user-visible behavior, not implementation details
- [ ] At least one meaningful assertion per test (not just "page loaded")
- [ ] Negative assertions where appropriate (element NOT visible, text NOT present)
- [ ] Assertion messages provide context for CI debugging
- [ ] `expect` with soft assertions used where multiple independent checks matter

### 2.5 CI Resilience
- [ ] Viewport is explicitly set (not relying on default)
- [ ] No dependence on specific execution speed (faster machine ≠ broken test)
- [ ] Network conditions mocked or controlled where relevant
- [ ] Test timeout is appropriate for CI (longer than local, but not infinite)
- [ ] Retries configured (typically 1-2 in CI) but not masking real flakiness

### 2.6 Diagnosability
- [ ] `trace: 'on-first-retry'` or equivalent configured
- [ ] Screenshot on failure configured
- [ ] Test steps are logically grouped (not one 100-line test with no structure)
- [ ] Descriptive test names that explain the scenario
- [ ] Error messages include the actual vs expected values

### 2.7 Fixture Design
- [ ] Fixtures are bounded: setup what's needed, nothing more
- [ ] Login/session state created once per worker (`storageState`) not per test
- [ ] Fixture setup failures are distinguishable from test failures
- [ ] Expensive setup (DB seeding, API calls) is done efficiently (global setup, not beforeEach)

### 2.8 Execution Efficiency
- [ ] Start with the smallest relevant test/file and one browser project
- [ ] Reuse the local web server and worker-scoped authentication state
- [ ] Capture traces on first retry or retain them only on failure; do not rerun the full suite solely to collect traces
- [ ] Keep inner-loop reporters and artifacts lightweight
- [ ] Expand to the full suite and browser matrix only after targeted verification passes

---

## 3. Debug Heuristics

### Pattern: Test Passes Locally, Fails in CI
- **Symptom**: Green locally, red in CI, no code changes
- **Common causes**: CI machine slower (race conditions exposed), different viewport, different OS/browser version, resource contention from parallel tests, network latency
- **Diagnose**: Run with `--trace on` in CI. Compare trace timeline between local and CI. Check for `waitForTimeout` or fixed timing assumptions. Check if test passes when run alone in CI (parallelism issue).
- **Fix**: Replace fixed waits with condition-based waits; set explicit viewport; isolate shared resources; ensure test passes alone in CI first

### Pattern: Element Found But Not Actionable
- **Symptom**: `element is not visible`, `element is outside of the viewport`, `element is detached from DOM`
- **Common causes**: Element still animating, covered by overlay/modal, re-rendered between find and action, lazy-loaded
- **Diagnose**: Check trace — what is covering the element? Is the element in the viewport? Is there an animation or transition in progress?
- **Fix**: Wait for stable state before action; scroll into view if needed; close overlays/modals first; wait for animation end

### Pattern: Intermittent Timeout
- **Symptom**: `waitForSelector` or `waitForResponse` times out randomly
- **Common causes**: Slow API response, lazy-loaded content, debounced search, dynamic rendering delay
- **Diagnose**: Check the trace for network timing and rendering timeline. Is the response slow? Is the element rendered after data arrives?
- **Fix**: Synchronize on the actual network or UI condition, for example a response followed by the resulting visible state. Treat a larger timeout as a temporary diagnostic or mitigation unless evidence proves the existing time budget is incorrect.

### Pattern: Stale Element Reference
- **Symptom**: Actions fail after page re-render, SPA navigation, or reactive UI updates
- **Common causes**: Element found before a reactive update, then DOM replaced; SPA page transition; virtual scrolling
- **Diagnose**: Trace whether the page re-rendered between `locator()` call and action. Check for framework reactivity.
- **Fix**: Re-query the element after navigation/update; wait for network idle after actions that trigger re-render

---

## 4. Error Patterns

| Error | Meaning | Common Causes | Fix Direction |
|-------|---------|---------------|---------------|
| `TimeoutError: waiting for locator` | Element never appeared or became actionable | Element not rendered, wrong page, slow response, animation blocking | Check page state at timeout; verify URL and causal readiness condition; change timeout only when the time budget is proven wrong |
| `Error: strict mode violation` | Locator matched multiple elements | Ambiguous selector, duplicate elements in DOM | Use more specific locator; use `.first()` if intentional |
| `Element is not visible` | Element in DOM but hidden or covered | CSS display:none, overlay, off-screen, opacity:0 | Wait for visibility; close overlay; scroll into view |
| `Element is outside of the viewport` | Element exists but not scrollable to | Fixed header covering, virtual scroll, off-screen position | Scroll into view; check for fixed headers offsetting click target |
| `Target closed` | Browser or page closed during test | Navigation after page close, popup closed, test teardown | Check navigation timing; handle popups explicitly; verify test lifecycle |
| `NS_ERROR_NOT_AVAILABLE` | Browser context destroyed | Browser crash, memory exhaustion, CI resource limit | Check CI memory; reduce parallel workers; check for browser leaks |

---

## 5. Refactor Guidelines

When refactoring Playwright tests, verify:
- [ ] Locator strategy unchanged or improved: new locators resolve to same elements
- [ ] Wait behavior preserved: no new fixed waits introduced
- [ ] Test isolation maintained: no new shared state between tests
- [ ] Fixtures refactored without breaking test independence
- [ ] Test names still accurately describe the scenario
- [ ] Trace/screenshot config preserved
- [ ] Parallel execution still safe after refactoring

---

## 6. Verification Rules

- [ ] Run deterministic fixes once, then run the containing file/project once
- [ ] Choose repeat counts from observed failure frequency, execution cost, and confidence needed; state the rationale
- [ ] Use one consistent repeat count for each verification stage and increase it only when the evidence requires greater confidence
- [ ] Run test alone: passes without other tests (catches order dependence)
- [ ] Run in parallel when shared-state or contention risk exists
- [ ] Inspect a retained failure trace when ordinary failure output is insufficient
- [ ] Cross-browser: test passes on all target browsers if applicable
- [ ] CI run: test passes in CI environment (not just locally)
