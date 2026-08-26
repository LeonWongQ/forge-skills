# Domain: MySQL

## 1. Activation

Load this domain when the task involves SQL queries, schema design, indexes, migrations, database transactions, locking, or data integrity at the MySQL layer.

**Auto-detect signals**: SQL statements, `@Query` annotations, MyBatis/JDBC/JPA usage, `EXPLAIN` output, migration files, `DataIntegrityViolationException`, `DeadlockLoserDataAccessException`, schema DDL.

---

## 2. Review Checklist

When reviewing MySQL-related code, verify each item.

### 2.1 Query and Index Alignment
- [ ] Every query in WHERE/JOIN/ORDER BY has a supporting index
- [ ] Leading index column order matches the actual query pattern
- [ ] No function-wrapped indexed columns in WHERE (`WHERE DATE(create_time) = ...`)
- [ ] No leading wildcard LIKE (`LIKE '%keyword'`) on large tables
- [ ] SELECT column list is minimal — no `SELECT *` on wide tables
- [ ] JOIN columns are indexed on both sides
- [ ] Pagination uses deterministic ORDER BY (unique column included)

### 2.2 Transaction and Locking
- [ ] Transaction duration is short — no remote calls, file I/O, or user waits inside transaction
- [ ] Isolation level is intentional for the consistency requirement
- [ ] Read-modify-write flows: is `SELECT ... FOR UPDATE` needed?
- [ ] Lock ordering is consistent across all code paths (prevents deadlocks)
- [ ] Batch updates: row lock escalation risk assessed
- [ ] No `LOCK TABLES` in application code (use transactions instead)

### 2.3 Schema Design
- [ ] Uniqueness constraints on columns that must be unique (don't rely on application code)
- [ ] NOT NULL on columns that should never be null
- [ ] Foreign keys or explicit referential integrity strategy
- [ ] Appropriate data types (VARCHAR length, INT vs BIGINT, DECIMAL for money)
- [ ] Default values are explicit and safe
- [ ] Soft-delete columns have appropriate indexes

### 2.4 Migration Safety
- [ ] Migration is backward-compatible with current application code
- [ ] No `DROP COLUMN` before all code paths stop reading/writing it
- [ ] Adding NOT NULL column: has a DEFAULT or is done in phases
- [ ] Large table ALTER: assessed for lock duration / replication lag
- [ ] Index creation: `ALGORITHM=INPLACE, LOCK=NONE` where possible
- [ ] Rollback plan exists and is tested

### 2.5 Consistency and Application Interaction
- [ ] Database is the authoritative source of truth for invariants
- [ ] Application-level uniqueness checks are backed by DB constraints
- [ ] Read-then-insert patterns: race condition assessed
- [ ] Cache invalidation happens AFTER database commit, not before
- [ ] Retry logic is idempotent at the database level

### 2.6 Query Performance
- [ ] N+1 queries eliminated (batch fetch or JOIN instead of per-row queries)
- [ ] Large OFFSET pagination replaced with keyset/cursor pagination
- [ ] Aggregation queries have appropriate indexes
- [ ] EXPLAIN reviewed for each query: type=ALL (full scan) is justified
- [ ] Query plan does not change significantly with data growth

---

## 3. Debug Heuristics

### Pattern: Slow Query
- **Symptom**: Query takes longer than expected, especially under load
- **Diagnose**: Run `EXPLAIN` — check for `type: ALL` (full scan), `rows` estimate, `Extra: Using filesort` / `Using temporary`. Check if the actual index is being used (key column in EXPLAIN).
- **Fix**: Add or reorder composite index to match WHERE + ORDER BY; rewrite non-sargable predicates; add covering index if SELECT list is narrow

### Pattern: Deadlock
- **Symptom**: `Deadlock found when trying to get lock; try restarting transaction`
- **Diagnose**: `SHOW ENGINE INNODB STATUS` — find the two transactions and which locks they held/waited for. Trace the lock ordering in application code.
- **Fix**: Consistent lock ordering across all code paths; reduce transaction duration; use `SELECT ... FOR UPDATE` earlier in the transaction

### Pattern: Lock Wait Timeout
- **Symptom**: `Lock wait timeout exceeded; try restarting transaction`
- **Diagnose**: Find the blocking transaction (`SHOW PROCESSLIST`, `sys.innodb_lock_waits`). What is it doing? Why is it holding locks so long?
- **Fix**: Shorten the blocking transaction; add missing index to reduce rows locked; split batch operations

### Pattern: Data Integrity Violation
- **Symptom**: `Duplicate entry for key`, `Column 'X' cannot be null`, `foreign key constraint fails`
- **Diagnose**: Trace the data flow. Is it a race condition (concurrent inserts)? Missing validation? Incorrect upsert logic?
- **Fix**: Add application-level pre-check + DB constraint (belt and suspenders); use `INSERT ... ON DUPLICATE KEY UPDATE` for upserts

### Pattern: Replication Lag
- **Symptom**: Read-after-write: data written but not visible on read replica
- **Diagnose**: Check replica lag. Is the read hitting a replica when it should hit primary?
- **Fix**: Route read-after-write to primary; use `@Transactional(readOnly = false)` for write+read consistency

---

## 4. Error Patterns

| Error | Meaning | Common Causes | Fix Direction |
|-------|---------|---------------|---------------|
| `DeadlockLoserDataAccessException` | MySQL deadlock, transaction rolled back | Inconsistent lock ordering, long transactions | Consistent lock order; retry with backoff |
| `CannotAcquireLockException` | Lock wait timeout | Row lock held by long transaction | Shorten transaction; add index to reduce locks |
| `DuplicateKeyException` | Unique constraint violated | Race condition, missing check, incorrect upsert | Add pre-check; use ON DUPLICATE KEY UPDATE |
| `DataIntegrityViolationException` | Constraint violation (NOT NULL, FK, etc.) | Missing validation, schema mismatch | Validate before persist; check entity state |
| `DataTruncation` | Value too long for column | Input exceeds column length | Truncate or increase column size |
| `CommunicationsException` | Connection lost to MySQL | Network issue, server restart, timeout | Connection pool validation; retry; health check |
| `QueryTimeoutException` | Query exceeded timeout | Missing index, data growth, lock contention | Add index; paginate; increase timeout |

---

## 5. Refactor Guidelines

When refactoring database code, verify:
- [ ] Query behavior preserved: same WHERE/JOIN/ORDER semantics
- [ ] Transaction boundaries preserved: no change to commit/rollback timing
- [ ] Lock ordering preserved: no new deadlock paths introduced
- [ ] Migration backward-compatible: old app code still works with new schema
- [ ] Index equivalence: new query patterns have appropriate indexes
- [ ] Connection/transaction scope unchanged: no accidental connection leaks

---

## 6. Verification Rules

- [ ] `EXPLAIN` output reviewed for each query in the change
- [ ] Representative data volume tested (not just empty tables)
- [ ] Concurrent access scenario walked through (race conditions, deadlocks)
- [ ] Migration tested with production-like data size
- [ ] Rollback tested
- [ ] Read-after-write consistency verified if using replicas
