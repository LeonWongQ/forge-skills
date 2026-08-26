# Playwright Failure Diagnosis

Read this reference for an existing failure, CI-only issue, or flakiness investigation.

Capture the exact error and stack, test step, locator, URL, browser, viewport, worker/retry configuration, trace or screenshot availability, and local-versus-CI conditions. Read the relevant test and page/component implementation before changing waits or selectors.

Rank hypotheses from evidence. Typical classes are missing state or wrong route for timeouts, ambiguous locators for strict-mode errors, overlays or transitions for actionability failures, environment/resource differences for CI-only failures, and leaked state or races for intermittence. Root cause must describe trigger, mechanism, and enabling condition.

After a deterministic fix, run the exact test once and its containing file/project once. Use three repeats only when testing a timing/shared-state theory. Use ten or more repeats and parallel checks only for confirmed flakiness or an explicit release gate. Report what ran and what remains unverified.
