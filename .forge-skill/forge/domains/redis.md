# Domain: Redis

## 1. Activation

Load this domain when the task involves Redis caching, key design, TTL strategy, cache invalidation, distributed locks, or Redis-based coordination.

**Auto-detect signals**: `RedisTemplate`, `StringRedisTemplate`, `@Cacheable`, `@CacheEvict`, `@CachePut`, Jedis/Lettuce imports, cache key construction code, TTL/expire settings.

---

## 2. Review Checklist

When reviewing Redis-related code, verify each item.

### 2.1 Cache Consistency
- [ ] Consistency model is explicit: is this best-effort, eventually consistent, or near-strongly consistent?
- [ ] Cache invalidation happens AFTER database commit, never before
- [ ] All write paths invalidate the cache (no missed paths)
- [ ] Stale read window is documented and acceptable for the business case
- [ ] Cache-aside pattern: read → cache miss → load from DB → populate cache (no race with concurrent writes?)
- [ ] Write-through vs write-behind: is the choice intentional? Are failure modes handled?

### 2.2 Key Design
- [ ] Keys encode the correct identity boundary (tenant, user, environment, version)
- [ ] Key naming convention is consistent (`namespace:entity:id` or similar)
- [ ] No key collisions across different data scopes or environments
- [ ] Bulk invalidation is possible (key pattern or namespace-based)
- [ ] Keys are human-readable enough for operations and debugging

### 2.3 TTL Strategy
- [ ] Every key has a TTL — no keys live forever without justification
- [ ] TTL has a rationale: business freshness requirement, memory budget, or both
- [ ] TTL is not so short it causes miss storms under normal traffic
- [ ] TTL is not so long that stale data persists beyond acceptable window
- [ ] TTL jitter: keys that expire simultaneously have randomized TTL (±10-20%) to prevent synchronized expiry

### 2.4 Invalidation
- [ ] Invalidation is atomic for multi-key logical entities (Lua script or pipeline if needed)
- [ ] Partial invalidation scenarios handled: what if only some keys are deleted?
- [ ] Invalidation on related data: when entity A changes, are entity B's cached references invalidated?
- [ ] No "delete then immediate repopulation" race during concurrent writes
- [ ] `@CacheEvict` annotations cover all update/delete paths

### 2.5 Stampede and Breakdown Protection
- [ ] Hot keys: identified and protected (local cache, request coalescing, probabilistic early recompute)
- [ ] Cache stampede: concurrent misses on same key coalesced (not N simultaneous DB loads)
- [ ] Cache breakdown: key that's never cached due to missing data — null cache or bloom filter?
- [ ] Cache penetration: malicious queries for non-existent keys hitting DB — null value caching?

### 2.6 Failure Handling
- [ ] Redis outage does not cause total application failure
- [ ] Cache miss on error: graceful degradation, not exception propagation
- [ ] Fallback strategy: stale cache, direct DB, or degraded response?
- [ ] Circuit breaker or timeout on Redis calls
- [ ] Retry strategy: backoff, max attempts, not retrying on write errors indiscriminately

### 2.7 Distributed Locks (if applicable)
- [ ] Lock has a TTL — process crash won't deadlock all waiters
- [ ] Unlock validates ownership (only the lock holder can unlock)
- [ ] Lock is not used as a substitute for proper data integrity constraints
- [ ] Lock timeout is appropriate for the protected operation duration
- [ ] Redisson or similar library used instead of raw SET NX (handles edge cases)

### 2.8 Memory and Operations
- [ ] Key count is bounded — no unbounded growth pattern
- [ ] Value size is reasonable (no multi-MB serialized objects)
- [ ] Memory usage monitored and alertable
- [ ] Eviction policy set (allkeys-lru or volatile-lru typically)

---

## 3. Debug Heuristics

### Pattern: Stale Data After Update
- **Symptom**: User updates data, but old data is still returned
- **Common causes**: Invalidation before commit (rollback leaves stale cache), missing invalidation on one write path, race between invalidation and concurrent repopulation, cache key mismatch
- **Diagnose**: Trace the write path — is invalidation after commit? Are all write paths covered? Is the cache key consistent between read and write?
- **Fix**: Move invalidation to after commit success; use `@TransactionalEventListener` (phase = AFTER_COMMIT); audit all write paths for cache eviction

### Pattern: Cache Miss Storm
- **Symptom**: Sudden spike in database load after cache keys expire
- **Common causes**: Many keys with same TTL expiring simultaneously, hot key eviction, Redis restart flushing all keys
- **Diagnose**: Check TTL distribution — are they all the same? Check Redis memory and eviction events. Identify the hot keys.
- **Fix**: TTL jitter; request coalescing (single loader for concurrent misses); local caffeine cache as first line; pre-warm cache after deploy

### Pattern: Redis Connection Failure
- **Symptom**: `RedisConnectionFailureException`, `RedisTimeoutException`
- **Common causes**: Redis server overloaded, network issue, connection pool exhausted, slow command blocking
- **Diagnose**: Check Redis server metrics (CPU, memory, slowlog, connected clients). Check connection pool config. Check for KEYS command or large payloads.
- **Fix**: Increase connection pool; add circuit breaker; optimize slow commands; ensure fallback path works

### Pattern: Lock Not Released
- **Symptom**: Application hangs waiting for lock that never releases
- **Common causes**: Process crashed while holding lock (no TTL), lock TTL too short (operation exceeds TTL), wrong unlock key
- **Diagnose**: Check Redis for orphaned lock keys. Check lock TTL vs actual operation duration. Verify unlock uses same key and value.
- **Fix**: Always set reasonable lock TTL; use Redisson's watchdog (auto-renewal); validate ownership on unlock

---

## 4. Error Patterns

| Error | Meaning | Common Causes | Fix Direction |
|-------|---------|---------------|---------------|
| `RedisConnectionFailureException` | Cannot connect to Redis | Server down, network, config wrong | Check Redis host/port; verify connectivity; add fallback |
| `RedisTimeoutException` | Command timed out | Slow command, server overload, network | Check slowlog; increase timeout; optimize command |
| `OOM command not allowed` | Redis memory limit reached | Unbounded key growth, no eviction policy | Set maxmemory-policy; add TTL; reduce key count |
| `READONLY` error | Writing to read-only replica | Misconfigured topology | Point writes to primary node |
| Stale data (no exception) | Cache not invalidated | Invalidation timing, missing path | Move invalidation after commit; audit write paths |
| Cache stampede (no exception) | DB overload on miss | Synchronized TTL expiry, hot key | TTL jitter; request coalescing; local cache |
| Lock timeout (no exception) | Lock not released in time | Operation too slow, deadlock | Increase lock TTL; optimize locked operation |

---

## 5. Refactor Guidelines

When refactoring Redis code, verify:
- [ ] Cache key format unchanged — or migration plan for old keys
- [ ] TTL behavior preserved — no change to staleness window
- [ ] Invalidation timing preserved — still happens after commit
- [ ] All write paths still invalidate — new code paths added?
- [ ] Serialization format compatible — old cached values still deserializable?
- [ ] Lock behavior preserved — lock TTL and ownership validation unchanged

---

## 6. Verification Rules

- [ ] Write + read race: write data → immediately read (before cache invalidation? after?)
- [ ] Invalidation timing: verify cache is empty after commit, not before
- [ ] Multi-path write: every write/update/delete path tested for cache eviction
- [ ] Redis down scenario: application degrades gracefully, no cascading failure
- [ ] TTL: key actually expires at expected time
- [ ] Concurrent miss: multiple callers miss same key simultaneously — only one DB load
