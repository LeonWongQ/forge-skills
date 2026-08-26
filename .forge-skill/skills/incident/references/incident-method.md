# Incident Response Method

## Triage

Confirm user-visible impact, affected regions/tenants/features, error or latency change, data integrity risk, start time, and whether impact is ongoing. Assign operational severity from impact, not technical novelty.

## Evidence and Hypotheses

Collect metrics, logs, traces, deploy/config changes, dependency health, capacity, and recent operational actions. Preserve timestamps and sources. Rank hypotheses by explanatory power, evidence, and test cost. Use one discriminating check at a time where possible.

## Mitigation

Prefer traffic reduction, rollback, feature disablement, isolation, or capacity relief when they are safer than live repair. Verify both user impact and system health, watch for delayed recurrence, and preserve rollback ability.

## Postmortem

Explain trigger, mechanism, enabling condition, blast radius, detection, response, and recovery. Separate prevention, detection, mitigation, and process actions. Each action needs an owner, due condition, verification method, and priority.
