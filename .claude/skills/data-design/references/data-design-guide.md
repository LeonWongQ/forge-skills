# Data Design Guide

## Schema

Identify entities, attributes, ownership, cardinality, lifecycle, and business keys. Target third normal form for ordinary OLTP unless a documented read pattern justifies controlled duplication. Use realistic string bounds, exact numerics for money, timezone-aware temporal semantics, and nullable fields only when absence has a defined meaning.

Use primary keys, unique constraints, foreign keys, checks, and defaults according to target-engine capability and operational requirements. Do not rely solely on application checks for invariants exposed to concurrent writers.

## Indexes and Queries

Derive an index from a concrete filter, join, ordering, or grouping pattern. For composite indexes, evaluate equality predicates, range predicates, ordering, selectivity, covering benefit, and write amplification together. Verify non-trivial queries with the target engine's execution plan and realistic cardinality.

Prefer keyset pagination for deep, stable ordered traversal. Use `EXISTS` for presence checks and handle nullable anti-joins explicitly. Diagnose N+1 access at the application boundary rather than hiding it with broad eager loading.

## Evolution

For online change, prefer expand, dual-compatible deployment, backfill with checkpoints, validation, traffic/read switch, and later contract. Define rollback only while old representations remain usable. Once data is discarded or irreversibly transformed, use tested restore or forward repair instead of a fictional `DOWN` script.

Estimate current and future rows, hot-set size, read/write ratio, retention, replication, and maintenance windows. Partitioning, sharding, replicas, and caches require evidence that a simpler design no longer meets the target.
