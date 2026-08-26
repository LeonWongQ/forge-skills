---
name: contract-compatibility
description: >-
  Assess API and event contract compatibility across producer and consumer versions.
  Use for API contract compatibility, event schema compatibility, breaking API/event
  changes, consumer compatibility, 接口契约兼容性, 事件契约兼容性, or 消费者兼容性.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls)]
---

# Contract Compatibility

## Activation

1. Load Forge kernel and autoload policy.
2. Classify API versus event, producer versus consumer, and the protected compatibility direction.
3. Load `domain.api_event_contracts` and `domain.testing`; add technology domains only when artifacts require them.
4. Inspect registered contract schemas and fixtures. Run `forge validate --check contracts` when artifacts are present.
5. Separate fixture-proven payload compatibility from runtime assumptions.

## Boundaries

- **architecture-design** designs a new API, event topology, or versioning strategy.
- **migration** owns broad upgrade, rollout, and rollback transitions.
- **test-design** owns broad test planning.
- **release-readiness** owns final production Go/No-Go decisions.

This skill assesses preservation of a declared API/event baseline and recommends remediation, verification, and safe transition sequencing.

## Output

```text
## Contract Scope and Parties
## Compatibility Direction Matrix
## Verified Fixture Evidence
## API/Event Semantic Risks
## Consumer Impact and Rollout
## Remediation and Verification Plan
## Unverified Runtime Assumptions
```

## Guard

- [ ] Baseline/current artifacts and compatibility direction are explicit.
- [ ] Consumer impact is assessed without assuming complete discovery.
- [ ] Fixture results are scoped to declared JSON payloads.
- [ ] Runtime ordering, idempotency, delivery, and rollout claims have separate evidence.
