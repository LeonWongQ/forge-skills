# Contract Compatibility Checklist

- [ ] Producers, consumers, baseline/current versions, and protected direction are named.
- [ ] Registered baseline/current schemas and representative fixtures cover the compatibility claim.
- [ ] Requiredness, nullability, defaults, unknown fields, enums, and version envelopes are assessed.
- [ ] API errors, pagination, and idempotency are reviewed where relevant.
- [ ] Event ordering, duplicate/replay, retry, DLQ, retention, and backfill assumptions are reviewed where relevant.
- [ ] Rollout, deprecation, rollback, telemetry, and residual external-consumer uncertainty are explicit.
- [ ] Fixture validation evidence is not presented as proof of runtime behavior.
