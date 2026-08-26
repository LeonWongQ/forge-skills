---
name: page-test
description: >-
  Write, review, auto-execute, and diagnose page/UI E2E tests using Playwright.
  Covers test case design, locator strategy, auto-wait assertions, isolation,
  CI resilience, flaky test diagnosis, and read-only page content extraction.
  Can run Playwright tests automatically to collect evidence, then diagnose.
  Use when the user says: write a page test, create a UI test, add Playwright test,
  write E2E test, test this page, create browser test, add page automation,
  test this flow in the browser, UI test, frontend test, web test,
  read page content with Playwright, extract page content, use Playwright to visit a URL,
  help me write a test for this page, design page test cases,
  this Playwright test fails, debug Playwright, diagnose UI test failure,
  写页面测试, 写UI测试, 写E2E测试, 写前端测试, 页面自动化测试,
  前端测试用例, 帮我写一个浏览器测试, 这个Playwright测试为什么失败,
  Playwright测试不稳定, UI测试偶发失败, 前端测试排查, 页面测试调试.
  For any page/UI test authoring, test execution, or browser test debugging.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls, npx playwright test *, npx playwright show-*, npx playwright codegen, node *, npm ci --ignore-scripts *, cat, head, tail), Write]
---

# Page Test

## Safety Gate

A direct request to open one exact URL and extract visible content authorizes one read-only navigation. Do not require another confirmation when there are no clicks, submissions, downloads, authentication changes, or other interactions.

All other browser test execution requires bounded authorization before the first run unless the selected test is explicitly marked `@safe`. State the environment, exact files/tests, known side effects, and a maximum of five targeted reruns. Authorization expires when any of those boundaries changes.

Never infer safety from HTTP methods alone. An apparently read-only request can still mutate data. Read [references/execution-policy.md](references/execution-policy.md) before running tests or interacting with a page.

## Route

Classify the request before loading details:

- Exact URL content extraction: use the read-only utility path below.
- New Playwright test: read [references/test-authoring.md](references/test-authoring.md).
- Existing failure or flaky test: read [references/diagnosis.md](references/diagnosis.md).
- Auto-execute and fix: read both diagnosis and execution-policy references.
- Review an existing test without changing it: use `code-review` with the Playwright domain.
- Component or unit testing: use `test-implementation`.

Load `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`, `.claude/forge/domains/playwright.md`, and `.claude/forge/domains/testing.md` only when the selected path needs them.

## Standalone Browser Runtime

Use the Skill-owned `playwright-core` only for ad hoc navigation, extraction, timing, and lightweight evidence. Use the target project's own `@playwright/test` version for project E2E tests.

For standalone work:

1. Run from this Skill directory.
2. If `node_modules/playwright-core` is absent, install only the lockfile dependency with `npm ci --ignore-scripts --no-audit --no-fund`.
3. Never run `playwright install`, `npx playwright install`, `npm exec playwright install`, or any browser download equivalent.
4. Detect an existing Chrome, Edge, or Chromium executable and pass it through `executablePath`.
5. If none exists, stop with `BROWSER_NOT_FOUND`; do not install or offer to install a browser.

Use `node scripts/read-page.mjs --inventory` for inventory and `node scripts/read-page.mjs --url <url> [--selector <selector>]` for one read-only extraction. Report dependency preparation separately from launch, navigation, extraction, and total browser time.

## Authoring Invariants

Keep generated tests behavior-focused and isolated:

- Prefer `getByRole`, `getByLabel`, visible text, and stable test IDs over CSS, XPath, or position selectors.
- Use Playwright auto-waiting and web-first assertions; do not add fixed sleeps or `waitForTimeout`.
- Give each test at least one meaningful user-visible assertion.
- Make tests independent and runnable alone, in any order, and in parallel where supported.
- Keep project configuration, fixtures, and dependency versions owned by the target project.

## Diagnosis Invariants

Define the symptom from the exact error, test, step, environment, and frequency. Collect failure output before adding reruns. Rank multiple hypotheses and identify root cause as trigger, mechanism, and enabling condition.

Fix the cause, then verify proportionally: exact test once, containing file/project once, `--repeat-each=3` only for a timing or shared-state hypothesis, and larger repeat/parallel runs only for confirmed flakiness or a release gate.

## Delivery

For extraction, return only requested content and timing unless analysis was requested. For authoring, default to inline code and write a file only when the user authorized a path. For diagnosis, report symptom, evidence, ranked hypotheses, root cause, fix, verification, and residual risk.

Before delivery confirm that execution stayed within authorization, no browser was installed, no fixed waits were introduced, and verification claims match the runs actually performed.

## Vue Boundary

Vue version guidance belongs to the evidence-confirmed Vue Skill. `page-test` owns browser E2E behavior regardless of Vue version; component and unit tests remain with `test-implementation`.
