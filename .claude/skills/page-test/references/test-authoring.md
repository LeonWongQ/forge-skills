# Playwright Test Authoring

Read this reference when writing or materially changing a Playwright E2E test.

Identify the route, user flow, expected state, authentication, data setup, API dependencies, feature flags, and nearby tests before writing code. Separate confirmed behavior from assumptions.

Prioritize core journeys, important alternatives, boundaries, and error states. Keep each test focused on one observable behavior. Prefer role and accessible name, label, visible text, test ID, then placeholder. Avoid CSS classes, XPath, `nth-child`, and ambiguous text.

Use web-first assertions and navigation or response predicates. Never add fixed sleeps. Reset state through fixtures or setup that each test owns; do not depend on execution order or data produced by another test. Reuse worker-scoped authentication only when isolation remains explicit.

Before delivery confirm descriptive names, unique locators, meaningful assertions, no fixed waits, independent data, success and failure coverage, and compatibility with the target project's Playwright version. Default to inline output unless a target path was authorized.
