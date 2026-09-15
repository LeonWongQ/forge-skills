# Project Skill Training RC1

## Candidate Scope

`skill-training-rc1` is an experimental test candidate for the project-scoped
Forge Skill training loop:

```text
opt-in configuration
  -> final-result collection
  -> human record review
  -> Summary generation and review
  -> Overlay generation and review
  -> explicit LLM evaluation and publication
  -> manual activation
  -> project-scoped runtime guidance
  -> reviewed feedback and automatic disabling
```

The global Skill remains unchanged. Summary versions are knowledge artifacts,
not runtime instructions. Only one published and manually activated Overlay may
affect one project and Skill at a time.

## Acceptance Evidence

- The deterministic end-to-end acceptance test covers the complete lifecycle,
  including feedback-driven disabling after 11 reviewed Overlay-tagged records
  contain 4 exclusions.
- The full local quality gate covers strict UTF-8, sensitive-content checks,
  Skill quality, evaluation-corpus integrity, all eight Forge validations,
  routing regression, documentation facts, and the full pytest suite.
- Codex global installation dry-run reports all links unchanged, confirming the
  linked checkout is the active test installation.

## Tester Workflow

1. Create or update `.forge-skill/learning/config.json` in a disposable test
   project and list only the Skill being tested in `enabledSkills`.
2. Invoke that Forge Skill and confirm one final-result record appears in the
   review dashboard. Empty results and unlisted Skills must create no record.
3. Review the record, generate a Summary, and explicitly confirm or exclude its
   rules on the version page.
4. Create and review an Overlay. Configure the LLM endpoint and environment
   variable only when ready to spend a real model call.
5. Run evaluation and publication, inspect the evidence, then activate the
   Overlay manually. Publication alone must not change runtime behavior.
6. Invoke the same Skill in the same project. Confirm the new record contains
   the applied Overlay identity and that another project remains unaffected.
7. Disable the Overlay manually after the smoke test, or review at least 11
   Overlay-tagged records to exercise the feedback threshold.

Start and stop the local dashboard through Forge's natural-language review
service intent. The service is loopback-only and does not start automatically.

## Stop and Rollback

- Disable the active Overlay from the version page for an immediate runtime
  kill switch. The global Skill continues unchanged.
- Remove the Skill from the project's `enabledSkills` list to disable both
  Overlay loading and future collection for that Skill.
- Stop the review service when it is not in use.
- Switch away from the RC source revision only after the working tree is clean;
  linked host installations follow the selected source revision.

No rollback step requires deleting collected data. Project registrations may be
archived to remove them from default cross-project scans while retaining their
history.

## Known RC Limits

- Direct-host collection and Overlay application rely on the host following the
  Skill lifecycle instructions. Without a native host after-response hook,
  collection is intentionally best-effort and cannot claim 100 percent capture.
- Phase 7 automatic evaluation is provisional. Phase 9 still requires broader
  per-Skill cases, human judge calibration, a real configured-endpoint
  acceptance run, and richer per-case dashboard evidence.
- Only Skills with at least three compatible, read-only evaluation cases can
  pass automatic publication. Other Skills can still collect, summarize, and
  produce manually inspectable Overlay drafts.
- This candidate is suitable for controlled local testing, not unattended or
  production-wide activation.
