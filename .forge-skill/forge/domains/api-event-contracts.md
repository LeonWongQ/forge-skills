# API & Event Contracts

## Scope

Use this domain to assess compatibility between API/event producers and consumers across a declared baseline and current contract. It covers JSON payload shape and the operational questions that fixture validation cannot prove.

## Directionality

State both directions before judging a change:

- **baseline producer → current consumer**: historical payloads must still be accepted.
- **current producer → baseline consumer**: newly emitted payloads must remain acceptable to deployed consumers.

Do not call a change “backward compatible” without naming the protected direction and consumers.

## API compatibility

Assess request/response fields for requiredness, nullability, defaults, unknown fields, enum expansion, pagination/filter defaults, error/status envelopes, and idempotency. Shape-valid payloads can still be behaviorally incompatible; document semantic changes and client assumptions.

## Event compatibility

Assess envelope identity/version, payload evolution, producer/consumer rollout order, duplicate/replay behavior, ordering/partition-key assumptions, retries, DLQ/poison messages, retention, backfill, and correlation identifiers. JSON Schema fixtures do not prove broker delivery or side-effect safety.

## Evidence boundary

The contracts validator proves only declared fixture acceptance against registered JSON Schemas. It does not prove runtime behavior, external consumer inventory, security, latency, ordering, idempotency, deployment sequencing, or rollback safety. Use integration evidence, telemetry, and rollout planning for those claims.

## Guard

- [ ] Producer, consumer, baseline, and protected direction are named.
- [ ] Required/optional/null/default/unknown/enum evolution is assessed.
- [ ] API error and idempotency semantics are considered where relevant.
- [ ] Event replay, duplicate, ordering, retry, and DLQ assumptions are explicit.
- [ ] Fixture evidence and unverified runtime assumptions are separated.
