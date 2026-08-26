# Observability & Reliability

## Scope

This domain supplies technology-neutral engineering heuristics for observing, operating, and verifying production behavior. It is relevant to release readiness, incidents, migrations, optimization, and architecture work.

It does not define incident command procedures or release go/no-go policy; those belong to the relevant skill or pack.

## Evidence model

Before claiming a system is reliable or ready, identify:

- user-impact signals and the service-level objective or practical success criterion;
- the logs, metrics, traces, deployment events, and business signals that support the claim;
- the correlation/request identifiers needed to join evidence across service boundaries;
- evidence freshness, coverage gaps, and uncertainty.

Do not treat an absence of alerts as evidence of health if telemetry, alert routing, or traffic coverage is unknown.

## Telemetry quality

- Logs should be structured, searchable, and include stable correlation identifiers where applicable.
- Metrics should cover latency, traffic, errors, and saturation; high-cardinality labels need explicit cost and retention consideration.
- Traces should reveal critical dependency boundaries and failure propagation without exposing sensitive data.
- Dashboards should expose user impact and the operational signals needed to decide mitigation or rollback.
- Alerts should be actionable: a clear symptom, meaningful threshold, owner, escalation path, and runbook link.

## Resilience and recovery

Assess timeouts, retry bounds, backoff, idempotency, circuit breaking, load shedding, graceful degradation, and dependency isolation in the context of the actual failure mode. A retry without bounded cost or idempotency can amplify outages.

For a proposed change, identify observable rollback triggers and the signals that prove recovery after rollback.

## Verification

Match claims to evidence:

- release changes: compare before/after signals, deployment events, error rate, latency, and critical journeys;
- performance changes: measure the intended bottleneck and guard against shifted saturation elsewhere;
- incidents: preserve timeline evidence and distinguish mitigation from root-cause confirmation;
- migrations: verify old/new compatibility and monitor each phased rollout.

State which signals were checked, their observation window, and what remains unverified.

## Guard

- [ ] User impact and success criteria are explicit.
- [ ] Logs, metrics, traces, and alerts are assessed only where relevant.
- [ ] Sensitive telemetry and metric-cardinality cost are considered.
- [ ] Rollback signals and recovery verification are explicit for production changes.
- [ ] Reliability conclusions distinguish evidence from assumptions.
