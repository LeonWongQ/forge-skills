# Domain-Specific Error Patterns

Quick reference for mapping errors to likely causes. Load the corresponding forge domain for detailed heuristics.

## Java (`.forge-skill/forge/domains/java.md`)

| Error Pattern | Likely Causes |
|--------------|---------------|
| NullPointerException | Missing null guard, uninitialized field, Optional misuse, async completion with null |
| ClassCastException | Generic type erasure, incorrect wiring, deserialization type mismatch |
| ConcurrentModificationException | Collection modified during iteration, missing synchronization |
| OutOfMemoryError: Java heap | Memory leak (unclosed resources, growing caches), insufficient -Xmx |
| OutOfMemoryError: Metaspace | Excessive class loading, ClassLoader leak, too many dynamic proxies |
| StackOverflowError | Infinite recursion, deep call chain, circular dependency |
| NoClassDefFoundError | Missing dependency at runtime, version mismatch, classpath issue |
| IllegalArgumentException | Invalid argument, violated precondition, enum value mismatch |

## Spring (`.forge-skill/forge/domains/spring.md`)

| Error Pattern | Likely Causes |
|--------------|---------------|
| NoSuchBeanDefinitionException | Missing @Component/@Service/@Repository, component scan not covering package, missing @Configuration, conditional bean not activated |
| NoUniqueBeanDefinitionException | Multiple beans of same type, missing @Primary or @Qualifier |
| BeanCreationException | Circular dependency, @Autowired on non-bean class, constructor injection failure |
| Transactional rollback not working | Self-invocation bypassing proxy, checked exception not triggering rollback, wrong transaction manager |
| @Transactional not applying | Method called on `this` (self-invocation), method not public, class not a Spring bean, wrong transaction manager |
| ApplicationContext startup failure | Configuration property binding error, missing required properties, profile misconfiguration |
| DataIntegrityViolationException | Unique constraint violation, null in NOT NULL column, foreign key violation |
| LazyInitializationException | Entity accessed outside transaction/session, missing @Transactional on calling method |

## MySQL (`.forge-skill/forge/domains/mysql.md`)

| Error Pattern | Likely Causes |
|--------------|---------------|
| CommunicationsException / Communications link failure | Network issue, server down, connection timeout, firewall |
| Deadlock found when trying to get lock | Concurrent transactions locking rows in different order, long transactions |
| Lock wait timeout exceeded | Row lock held by another long-running transaction |
| Duplicate entry for key | Unique constraint violation, race condition on insert |
| Data truncated for column | Value too long for column definition, wrong charset |
| Too many connections | Connection pool exhausted, connections not released, max_connections reached |

## Redis (`.forge-skill/forge/domains/redis.md`)

| Error Pattern | Likely Causes |
|--------------|---------------|
| RedisConnectionFailureException | Redis server down, network issue, connection pool exhausted |
| RedisTimeoutException | Slow command, network latency, server overload |
| JedisConnectionException / LettuceConnectionException | Connection refused, timeout, authentication failure |
| OOM command not allowed when used memory > 'maxmemory' | Redis memory limit reached, eviction policy not effective |
| READONLY You can't write against a read only replica | Writing to replica node in cluster/sentinel, misconfigured topology |

## Testing (`.forge-skill/forge/domains/testing.md`)

| Error Pattern | Likely Causes |
|--------------|---------------|
| Test fails only in CI, passes locally | Environment difference (OS, locale, timezone), timing/concurrency, resource availability, order-dependent tests |
| Flaky test (intermittent failure) | Timing assumptions, shared mutable state, test order dependency, external service instability, random data |
| AssertionError: expected X but was Y | Logic error, test data mismatch, state leakage between tests |
| Mockito UnnecessaryStubbingException | Stubbed method never called, over-stubbing |
| Mockito Strict stubbing argument mismatch | Wrong arguments passed to mocked method |
