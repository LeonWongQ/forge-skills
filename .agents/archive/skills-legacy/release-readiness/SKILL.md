---
name: release-readiness
description: >-
  Assess whether a change is ready to release by reviewing test evidence,
  compatibility, observability, rollout, rollback, ownership, and unresolved
  risk. Use for release readiness, go/no-go, release gate, deployment review,
  发版就绪, 发布评审, 上线检查, 发布门禁, or 上线前评估.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls)]
context: inherit
---

# Release Readiness

## Activation

1. Load `.Codex/forge/AGENTS.md` and `.Codex/forge/AUTOLOAD.md`.
2. Inventory the proposed change, owners, dependencies, and deployment boundary.
3. Load `domain.testing` and `domain.observability_reliability`; add technology domains only when the change requires them.
4. Use the full workflow and the release-readiness checklist.
5. Deliver a bounded Go, No-Go, or Conditional Go decision with evidence and remaining uncertainty.

## Core Discipline

Release readiness aggregates evidence; it does not replace:

- **test-design** — creates coverage strategy;
- **report** — formats a report without owning the go/no-go assessment;
- **incident** — analyzes an active production failure;
- **migration** — plans a compatibility transition and rollback path.

Never infer readiness from passing tests alone. Evaluate test scope/freshness, compatibility, operational telemetry, rollout/rollback, owner readiness, and unresolved risk together.

## Required Assessment

- Change scope, affected systems, configuration/data changes, and non-goals.
- Current test evidence, critical-journey coverage, failures, skips, and accepted gaps.
- Compatibility and dependency risks.
- Dashboards, alerts, logs, traces, ownership, and runbooks for changed paths.
- Rollout approach, stop/rollback triggers, rollback steps, and recovery verification.
- Known defects, risk acceptance owner, and explicit release conditions.

## Output

```text
## Release Scope

## Evidence Summary

## Readiness Matrix
| Area | Evidence | Risk | Status | Owner / Condition |

## Rollout and Rollback

## Open Risks and Exceptions

## Decision
Go / No-Go / Conditional Go

## Verification Window
```

## Guard

- [ ] Evidence is specific and time-bounded.
- [ ] Unverified areas are visible rather than assumed safe.
- [ ] Rollback is actionable and has observable triggers.
- [ ] Decision owner and conditional-go criteria are explicit.
