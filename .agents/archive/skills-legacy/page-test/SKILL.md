---
name: page-test
description: >-
  Write, review, auto-execute, and diagnose page/UI E2E tests using Playwright.
  Covers test case design, locator strategy, auto-wait assertions, isolation,
  CI resilience, and flaky test diagnosis for browser automation.
  Can run Playwright tests automatically to collect evidence, then diagnose.
  Use when the user says: write a page test, create a UI test, add Playwright test,
  write E2E test, test this page, create browser test, add page automation,
  test this flow in the browser, UI test, frontend test, web test,
  help me write a test for this page, design page test cases,
  this Playwright test fails, debug Playwright, diagnose UI test failure,
  写页面测试, 写UI测试, 写E2E测试, 写前端测试, 页面自动化测试,
  前端测试用例, 帮我写一个浏览器测试, 这个Playwright测试为什么失败,
  Playwright测试不稳定, UI测试偶发失败, 前端测试排查, 页面测试调试.
  For any page/UI test authoring, test execution, or browser test debugging.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls, npx playwright test *, npx playwright show-*, npx playwright codegen, cat, head, tail), Write]
context: inherit
---

# Page Test

---

## ⛔ EXECUTION SAFETY GATE (READ THIS FIRST)

### The rule: ALL test execution requires your confirmation.

Real projects don't follow clean REST conventions — a `GET /api/export` could trigger side effects, and a `POST` could be a harmless search. We cannot reliably guess which tests mutate data from code analysis alone.

**Every time** this skill wants to run `npx playwright test`, it will:

1. List what will be executed (which test files / which tests)
2. State the detected environment (from `playwright.config.*` — `baseURL`, `webServer`)
3. Show a brief summary of what each test does
4. **Wait for your explicit "yes"** before running

### The only exception: `@safe` markers

If you annotate a test file or test block with `@safe`, it becomes pre-authorized for auto-execution:

```typescript
// @safe — read-only assertions, no DB side effects
test.describe('Login page rendering', () => {
  test('logo is visible', async ({ page }) => { ... });
  test('error shown on empty submit', async ({ page }) => { ... });
});
```

Or per-test:

```typescript
// @safe
test('dashboard loads without errors', async ({ page }) => { ... });
```

The skill will detect `@safe` markers, skip confirmation for those tests, and state "3 @safe tests auto-executed, 2 tests need confirmation."

### Confirmation format:

```
🔔  About to run Playwright tests:

  Environment: http://localhost:3000 (local dev server)
  Test files:
    1. login.spec.ts — Login page rendering, form validation, error states
    2. order.spec.ts — Create order flow (⚠️ will create order records)

  Known impact:
    - order.spec.ts creates test orders in local DB

  Run all? [y / safe-only / n]
```


---

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Classify the task intent:
   - **Write new page test** → Test Design path (section 3)
   - **Debug failing page test (user provides error)** → Diagnosis path (section 4)
   - **Auto-execute + diagnose (user wants us to run tests)** → Auto-Diagnosis path (section 5)
   - **Review existing page test** → delegate to `code-review` skill with domain.playwright active
   - **Ambiguous** → ask one minimal clarification, then route
3. **Check EXECUTION SAFETY GATE** — if the task involves running tests, every execution must be confirmed unless tests are marked `@safe`
4. Detect UI technology from project context:
   - Playwright config files (`playwright.config.*`) → `.Codex/forge/domains/playwright.md`
   - `@playwright/test` imports → `.Codex/forge/domains/playwright.md`
   - If no Playwright signal detected, confirm test framework with user before proceeding
5. Load `.Codex/forge/domains/testing.md` for test design principles
6. Compose forge modules per the selected path
7. Execute workflow
8. Deliver output

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Kernel | `.Codex/forge/AGENTS.md` | Universal engineering principles |
| Autoload | `.Codex/forge/AUTOLOAD.md` | Selective activation policy |
| Behavior (write) | `.Codex/forge/behaviors/document.md` | Primary: produce durable, correct test code |
| Behavior (debug) | `.Codex/forge/behaviors/debug.md` | Primary: diagnose test failures |
| Domains | `.Codex/forge/domains/playwright.md` | Playwright-specific: locators, waits, CI, traces |
| | `.Codex/forge/domains/testing.md` | Test quality: assertions, isolation, determinism |
| Workflow (write) | `workflow.full_default` | discover → evidence → context → reasoning → planning → execution → verification → delivery |
| Workflow (debug) | `workflow.debug_analysis` | symptom → evidence → hypotheses → root cause → fix |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/verification-checklist.md` | Claims justified and bounded |
| | `.Codex/forge/checklists/delivery-checklist.md` | Output is usable |

---

## 3. Test Design Path (Write New Page Test)

### 3.1 Discover: Understand the page under test

**Collect evidence before writing any test code:**
- What page/route/URL is being tested?
- What is the user flow? (happy path, alternative paths, error states)
- What UI elements are involved? (buttons, inputs, modals, toasts, tables, forms)
- What API calls does the page make? (network tab, route definitions)
- What is the expected state before the test? (auth, data, feature flags)
- What existing tests cover related flows?

**Output**: Clear specification of what behavior the test should verify.

### 3.2 Plan: Design the test structure

```
For each test file:
  ├── test.describe('Feature: <name>')
  │   ├── test.beforeEach — setup (auth, data, navigation)
  │   ├── test('Happy path: <scenario>') → P0
  │   ├── test('Alternative: <scenario>') → P1
  │   ├── test('Edge case: <scenario>') → P1
  │   └── test('Error state: <scenario>') → P2
```

**Priority rules:**
- **P0**: Core user journeys that must never break (block release if failing)
- **P1**: Important alternatives, boundary conditions, common error states
- **P2**: Rare edge cases, visual regressions, nice-to-have coverage

### 3.3 Design locator strategy (per Playwright domain)

Apply the locator quality rules from `.Codex/forge/domains/playwright.md`:

| Priority | Strategy | Example | Resilient? |
|----------|----------|---------|------------|
| 1st | `getByRole` + accessible name | `page.getByRole('button', { name: 'Submit' })` | ✅ Best |
| 2nd | `getByLabel` | `page.getByLabel('Email')` | ✅ |
| 3rd | `getByText` | `page.getByText('Welcome back')` | ✅ |
| 4th | `getByTestId` | `page.getByTestId('login-form')` | ✅ |
| 5th | `getByPlaceholder` | `page.getByPlaceholder('Search...')` | ⚠️ |
| Avoid | CSS class, nth-child, xpath | `.btn-primary`, `div:nth-child(3)` | ❌ |

**Every locator must**:
- resolve to exactly one element (Playwright strict mode is on by default)
- use the user-visible text/label, not implementation details
- survive minor UI refactors

### 3.4 Design wait strategy (per Playwright domain)

**Rule: ZERO fixed waits.** No `waitForTimeout`, no `sleep`, no `setTimeout`.

| Instead of | Use |
|-----------|-----|
| `await page.waitForTimeout(3000)` | `await expect(page.getByText('Loaded')).toBeVisible()` |
| `await sleep(1000)` after click | `await page.getByRole('button').click()` (auto-waits) |
| `await page.waitForTimeout(500)` for debounce | `await expect(page.getByText('Results')).toBeVisible({ timeout: 10000 })` |
| Fixed wait after navigation | `await page.waitForURL('**/dashboard')` or `await page.waitForLoadState('networkidle')` |

### 3.5 Design assertions

**Assertion discipline:**
- Verify **user-visible behavior**, not internal state
- At least one **meaningful assertion** per test (not just "page didn't crash")
- Prefer `expect` with specific matchers over manual checks
- Include **negative assertions** where absence matters
- Add **assertion messages** when the default error would be unclear

```typescript
// ❌ Weak: just checks page loaded
await expect(page.getByText('Dashboard')).toBeVisible();

// ✅ Strong: verifies the behavior
await expect(page.getByText('Dashboard')).toBeVisible();
await expect(page.getByTestId('user-greeting')).toHaveText('Hello, test user');
await expect(page.getByRole('button', { name: 'Create Order' })).toBeEnabled();
await expect(page.getByText('暂无数据')).not.toBeVisible();
```

### 3.6 Design isolation

- Each test is **independent**: can run alone, in any order, in parallel
- `beforeEach` resets all state (no shared mutable state between tests)
- Test data: create what you need or use isolated fixtures — never depend on data from another test
- Auth state: use `storageState` per worker, not per-test login

### 3.7 Write the test file

Output a complete, runnable Playwright test file with:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature: <feature-name>', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: auth, data seed, navigation
  });

  test('<scenario>: <expected outcome>', async ({ page }) => {
    // Arrange → Act → Assert
  });
});
```

### 3.8 Output guard for test design

Before delivering the test file:
- [ ] Every test has a descriptive name (scenario + expected outcome)
- [ ] Locators use semantic strategies (role/label/text/testId), not CSS/xpath
- [ ] Zero `waitForTimeout` or fixed sleeps
- [ ] At least one meaningful assertion per test
- [ ] Tests are independent (no order dependency, no shared mutable state)
- [ ] Happy path + at least one edge case + at least one error state covered
- [ ] **Default output**: display inline. Write to file only with user confirmation of path.

---

## 4. Diagnosis Path (Debug Failing Page Test)

### 4.1 Symptom definition

Extract precise failure info from the user:
- **What**: exact error message, screenshot, trace reference
- **Where**: which test, which step, which locator
- **When**: always / intermittent / only in CI / only locally
- **Conditions**: specific browser, viewport, parallel mode, data state

### 4.2 Evidence collection

Gather before interpreting:
- Full error message and stack trace
- Playwright trace (`--trace on`) if available
- Screenshot at failure point
- Test code (locators, wait strategy, assertions, setup)
- Page/component code under test
- CI vs local environment differences (viewport, timeout, workers, browser version)

### 4.3 Hypothesis formation

Generate MULTIPLE ranked hypotheses using Playwright-specific failure patterns:

| Pattern | Hypothesis priority |
|---------|-------------------|
| `TimeoutError: waiting for locator` | 1. Element never rendered 2. Wrong page/URL 3. Slow API response 4. Animation blocking |
| `Error: strict mode violation` | 1. Duplicate elements 2. Ambiguous selector |
| `Element is not visible` | 1. CSS hidden 2. Overlay/modal covering 3. Off-screen |
| `Element is outside of the viewport` | 1. Fixed header offset 2. Virtual scroll 3. Element position |
| Test passes locally, fails in CI | 1. Timing/race condition 2. Different viewport 3. Resource contention 4. Network latency |
| Intermittent failure | 1. Order dependence 2. Shared state leak 3. Race in code under test 4. External service instability |

For detailed patterns, refer to `.Codex/forge/domains/playwright.md` sections 3 and 4.

### 4.4 Root cause identification

Root cause = **trigger** + **mechanism** + **enabling condition** (from debug discipline).

### 4.5 Fix and verification

- Fix addresses the root cause, not the symptom (no `waitForTimeout` bandaids)
- Verification: run test 10+ times, alone and in parallel, locally and in CI

### 4.6 Output guard for diagnosis

Before delivering:
- [ ] Symptom precisely defined (what, where, when, conditions)
- [ ] Multiple ranked hypotheses, not one guess
- [ ] Root cause = trigger + mechanism + enabling condition
- [ ] Fix is Playwright-idiomatic (no `waitForTimeout`, no CSS selectors)
- [ ] Verification plan included

---

## 5. Auto-Diagnosis Path (Auto-Execute + Diagnose)

This path is triggered when the user asks this skill to find and fix test failures itself — no pre-existing error report provided.

### 5.1 Detect the test environment

```
Step 1: Find Playwright config
  → Glob: playwright.config.*
  → Read config to detect: testDir, baseURL, projects (browsers), webServer

Step 2: Check if dev server is already running
  → If webServer is configured → likely auto-started by Playwright
  → If not → check if baseURL is reachable, offer to start the dev server
```

### 5.2 Run the tests (with EXECUTION SAFETY GATE)

```
Step 3: Check for @safe markers
  → Scan test files for `// @safe` annotations
  → @safe tests → auto-execute silently
  → Non-@safe tests → show confirmation prompt (see GATE format above)

Step 4: After user confirms
  → npx playwright test --reporter=list
  → On failure: npx playwright test --trace on (capture trace for failed tests)

Step 5: If all pass
  → Report: "All N tests pass. Nothing to diagnose."
```

### 5.3 Collect and diagnose

```
Step 6: For each failed test
  → Read the test file (locators, steps, assertions)
  → Read the page/component under test
  → If trace available: npx playwright show-trace trace.zip
  → Apply Diagnosis Path (section 4): symptom → evidence → hypotheses → root cause → fix

Step 7: Apply fixes
  → Edit the test file with the fix
  → Re-run: npx playwright test --grep "<fixed test name>" --repeat-each=5
  → Confirm the fix is stable
```

### 5.4 Auto-Diagnosis guard

Before delivering:
- [ ] DB Safety Gate checked for every test executed
- [ ] Each failure has a root cause diagnosis (trigger + mechanism + condition)
- [ ] Each fix is verified by re-running the test
- [ ] Unfixable issues are escalated with clear explanation

---

## 6. Playwright Command Reference (for Bash execution)

| Command | Purpose | When to use |
|---------|---------|-------------|
| `npx playwright test` | Run all tests | First execution to see current state |
| `npx playwright test --grep "<name>"` | Run specific test | After fixing, to verify |
| `npx playwright test --trace on` | Run with trace capture | When you need the trace for diagnosis |
| `npx playwright test --reporter=list` | Concise output | Quick status check |
| `npx playwright test --headed` | Run with visible browser | When user wants to watch execution |
| `npx playwright test --repeat-each=10` | Run each test 10× | Catch flaky tests |
| `npx playwright show-trace trace.zip` | Open trace viewer | Deep-dive into failure timeline |
| `npx playwright test --project=chromium` | Run on specific browser | Cross-browser diagnosis |

---

## 7. Global Guard

- [ ] Task intent classified (write / debug / auto-diagnose / review)
- [ ] Playwright domain loaded for locator/wait/CI guidance
- [ ] Testing domain loaded for assertion/isolation/determinism
- [ ] Output matches the selected path
- [ ] Code output is runnable and follows project conventions
- [ ] **Execution Safety Gate**: any non-@safe test execution got explicit user confirmation

---

## 8. Quick Reference

| Scenario | Key Principle |
|----------|--------------|
| Choosing a locator | `getByRole` > `getByLabel` > `getByText` > `getByTestId` |
| Waiting for something | Condition-based wait, NEVER `waitForTimeout` |
| Test is flaky | Run 10× alone + 10× in parallel, check shared state |
| CI-only failure | Check viewport, timing, resource contention, worker count |
| Strict mode violation | Locator matches >1 element — use more specific locator |
| Element not actionable | Overlay/modal covering, animation in progress, off-screen |
| Test execution | ALL test runs require confirmation — unless the test is marked `// @safe` |

## Vue Version Integration

For Vue-related targets, identify the **target package** and verify its resolved `vue` version from its lockfile or installed dependency metadata before loading framework guidance. `package.json` is provisional when no resolved version is available; `.vue`, Vite, Composition API, `<script setup>`, Router, and `import.meta.env` are not version proof.

- Vue `2.0–2.6` → load `domain.vue2`; inspect compiler parity and, for vmd-ui, the resolved package version plus existing imports, registration, and CSS/theme usage.
- Vue `2.7.x` → load `domain.vue2_7`; verify the actual compiler and Vite-compatible plugin/toolchain before applying Vite advice.
- Vue `3.x` → load `domain.vue3_vite`.
- Missing or conflicting evidence → retain the current intent workflow and request the target package/version; do not mix version-specific lifecycle, reactivity, compiler, or build guidance.

`page-test` remains Playwright E2E-only, while component/unit testing remains with `test-implementation`.
