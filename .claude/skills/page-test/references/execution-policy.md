# Playwright Execution Policy

Read this reference before running a Playwright test or interacting with a page beyond one read-only navigation and extraction.

## Authorization

Before the first non-`@safe` run, state the resolved environment and base URL, selected files and exact tests when known, a short behavior and side-effect summary, and the initial run plus no more than five targeted reruns.

Accept `yes`, `safe-only`, or refusal. A change to environment, selected scope, browser matrix, side effects, or rerun budget requires new authorization. An `@safe` marker pre-authorizes only the marked read-only tests; report how many were selected automatically.

## Execution Scope

Discover the Playwright config and selected tests once, record a fingerprint, and reuse it until those files change. Prefer the exact test, then the file, then a broader project. Use Chromium first unless the issue is browser-specific. Reuse an existing development server when the project supports it.

Retain a trace on the first useful failure. Do not repeatedly rerun a test that already produced enough evidence. Full-suite, cross-browser, and high-repeat runs are final validation tools, not default diagnosis steps.

## Safety Boundaries

Do not click, submit, authenticate, download, mutate data, or run unknown tests under read-only navigation authorization. Do not classify a test as safe solely from `GET`, a filename, or a test title. Stop when impact cannot be bounded.

Never download a browser. Missing local Chrome, Edge, or Chromium is `BROWSER_NOT_FOUND`.
