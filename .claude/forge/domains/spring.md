# Domain: Spring

## 1. Activation

Load this domain when the task involves Spring annotations (`@Service`, `@Repository`, `@Controller`, `@Transactional`, `@Autowired`, `@Bean`, `@Configuration`), `application.yml`/`application.properties`, Spring Boot starters, or Spring framework classes in stack traces.

**Auto-detect signals**: `@Service`, `@Component`, `@Repository`, `@Controller`, `@RestController`, `@Transactional`, `@Autowired`, `@Qualifier`, `@Bean`, `@Configuration`, `@SpringBootApplication`, `application.yml`, `application.properties`, Spring Boot stack trace classes (`org.springframework.`).

---

## 2. Review Checklist

When reviewing Spring code, verify each item. Mark N/A if not applicable.

### 2.1 Dependency Injection
- [ ] `@Autowired` fields: prefer constructor injection over field injection (testability, clarity)
- [ ] `@Qualifier` used correctly: is the qualifier value unambiguous across modules?
- [ ] Circular dependencies: any bean A → B → A chains? (breaks constructor injection)
- [ ] Bean ambiguity: multiple beans of same type without `@Primary` or `@Qualifier`?
- [ ] Cross-module dependencies: are referenced beans guaranteed to be in the container?
- [ ] Method signature: does the called method actually exist on the injected interface?

### 2.2 Transactions
- [ ] `@Transactional` self-invocation: any method calling `this.transactionalMethod()` from within the same class? (proxy bypass — annotation won't apply)
- [ ] Transaction boundaries explicit: where does the transaction begin and end?
- [ ] Propagation: is `REQUIRED` vs `REQUIRES_NEW` vs `NESTED` intentional?
- [ ] Rollback triggers: checked exceptions do NOT trigger rollback by default — is this correct?
- [ ] Transaction duration: any remote calls, file I/O, or long loops inside transaction?
- [ ] Side effects before commit: cache updates, events, or messages sent before transaction commits? (will execute even on rollback)
- [ ] Read-only transactions: `@Transactional(readOnly = true)` for pure read operations

### 2.3 Proxy and AOP
- [ ] Self-invocation: any `this.method()` call where the method has `@Transactional`, `@Cacheable`, `@Async`, or `@EventListener`? (proxy bypass)
- [ ] Method visibility: annotated methods are `public`? (private/protected won't be proxied by default)
- [ ] Final methods: any `final` method with Spring AOP annotations? (CGLIB cannot proxy final)
- [ ] AOP ordering: multiple aspects on same method — is the order correct?

### 2.4 Bean Lifecycle and Scope
- [ ] Singleton beans with mutable state? (shared across all threads and requests — dangerous)
- [ ] Request-scoped beans injected into singletons? (requires proxy mode or ObjectFactory)
- [ ] `@PostConstruct`: any heavy initialization that could delay startup or fail silently?
- [ ] `@PreDestroy`: are resources properly released?
- [ ] Bean initialization order dependencies: are they explicit via `@DependsOn`?

### 2.5 Configuration
- [ ] `@Value` / `@ConfigurationProperties`: are properties validated? (`@Validated`, `@NotEmpty`, `@Min`)
- [ ] Default values: are they safe for production?
- [ ] Profile-specific config: is there hidden behavior that changes per environment?
- [ ] Sensitive values: passwords, tokens, keys — are they in property files? (use vault/secret manager)
- [ ] Timeouts, pool sizes, retry counts: are defaults appropriate for production load?

### 2.6 Controller and MVC
- [ ] Business logic in controller: any domain logic that belongs in a service?
- [ ] Input validation: `@Valid` / `@Validated` on request bodies? Custom validators for business rules?
- [ ] Exception exposure: do `@ExceptionHandler` or `@ControllerAdvice` leak internal details?
- [ ] HTTP status codes: do they accurately reflect the outcome? (404 vs 400 vs 500 vs 403)
- [ ] Response serialization: are internal fields accidentally exposed in JSON?

### 2.7 Async and Events
- [ ] `@Async` methods: do they assume transaction context? (transaction context is lost across async boundary)
- [ ] `@EventListener`: is the event published before or after transaction commit? Use `@TransactionalEventListener` if post-commit
- [ ] Event payload: is it immutable? Could it be modified after publication?
- [ ] Async executor configuration: are pool sizes and queue capacities explicit?

### 2.8 Layering
- [ ] Controller → Service → Repository separation: any layer bypass?
- [ ] Service responsibilities: one service orchestrating too many concerns?
- [ ] DTO vs Entity: are entities leaked to the presentation layer?

---

## 3. Debug Heuristics

### Pattern: Transaction Not Working
- **Symptom**: Data not persisted / not rolled back despite `@Transactional`
- **Common causes**: Self-invocation (most common), method not public, wrong transaction manager, checked exception not triggering rollback, transaction on caller not callee
- **Diagnose**: Check call path — is it going through a Spring proxy? Add a breakpoint in `TransactionInterceptor`. Verify the exception type.
- **Fix**: Restructure to call through injected reference, or use `AopContext.currentProxy()`, or make exception unchecked / add `rollbackFor`

### Pattern: NoSuchBeanDefinitionException
- **Symptom**: Application fails to start — "No qualifying bean of type X"
- **Common causes**: Missing `@Component`/`@Service` on implementation, component scan not covering package, conditional bean not activated, missing dependency module
- **Diagnose**: Check if the implementation class has the right annotation. Verify component scan base packages. Check `@ConditionalOnX` annotations.
- **Fix**: Add missing annotation; adjust component scan; ensure dependency is in pom.xml

### Pattern: BeanCreationException / Circular Dependency
- **Symptom**: Application fails to start with circular dependency error
- **Common causes**: Bean A depends on B, B depends on A (direct or indirect), both via constructor injection
- **Diagnose**: Trace the dependency chain. Constructor injection makes circular dependencies immediately visible.
- **Fix**: Break the cycle with setter injection on one side (short-term), extract a third bean (long-term), or use `@Lazy` on one dependency

### Pattern: LazyInitializationException
- **Symptom**: `LazyInitializationException` — "could not initialize proxy — no Session"
- **Common causes**: JPA entity accessed outside transaction boundary (e.g., in controller after service returned)
- **Diagnose**: Find where the lazy-loaded property is accessed. Trace the transaction boundary.
- **Fix**: Fetch required data inside transaction, use DTO projection, or use `@EntityGraph`

### Pattern: Configuration Not Taking Effect
- **Symptom**: Changed `application.yml` but behavior unchanged
- **Common causes**: Wrong profile active, property overridden in another file, environment variable override, caching
- **Diagnose**: Check active profiles. Check all property sources (command line > env vars > application-{profile}.yml > application.yml).
- **Fix**: Verify profile activation; use `@ConfigurationProperties` with validation for critical config

---

## 4. Error Patterns

| Error | Meaning | Common Causes | Fix Direction |
|-------|---------|---------------|---------------|
| `NoSuchBeanDefinitionException` | Spring cannot find the required bean | Missing annotation, component scan gap, missing dependency module | Add `@Service`/`@Component`; check scan packages; add Maven dependency |
| `NoUniqueBeanDefinitionException` | Multiple beans of same type found | Two implementations of same interface, no `@Primary` or `@Qualifier` | Add `@Primary` or use `@Qualifier` at injection point |
| `BeanCreationException` | Bean instantiation failed | Circular dependency, constructor arg not satisfiable, init method failed | Break cycle; check constructor parameters; check `@PostConstruct` |
| `TransactionSystemException` | Transaction infrastructure error | Wrong transaction manager, JTA misconfiguration, connection pool exhausted | Check DataSource configuration; verify transaction manager bean |
| `DataIntegrityViolationException` | Database constraint violated | Unique constraint, NOT NULL violation, FK constraint | Check entity state before persist; validate input |
| `LazyInitializationException` | Entity accessed outside session | Lazy-loaded property accessed after transaction closed | Fetch eagerly or inside transaction; use DTO |
| `HttpMessageNotReadableException` | Request body cannot be deserialized | JSON parse error, type mismatch, unknown property | Fix request format; add `@JsonIgnoreProperties` |
| `MethodArgumentNotValidException` | Validation on request argument failed | `@Valid` body with constraint violations | Fix input; check validation annotations |
| `BindException` | Property binding failed | `application.yml` value cannot be converted to target type | Fix property value; add `@ConfigurationProperties` validation |
| `AsyncRequestTimeoutException` | Async request timed out | Long-running async method, unconfigured timeout | Increase timeout; offload to message queue |

---

## 5. Refactor Guidelines

When refactoring Spring code, verify:
- [ ] Bean definitions preserved: no bean accidentally removed or renamed
- [ ] Injection points preserved: all `@Autowired`/constructor params still satisfied
- [ ] Transaction boundaries preserved: methods that were `@Transactional` remain so; no new self-invocation introduced
- [ ] Proxy behavior unchanged: if a method was called through proxy, it still is
- [ ] Configuration keys unchanged: `@Value` and `@ConfigurationProperties` keys still resolve
- [ ] Controller endpoints unchanged: URL mappings, HTTP methods, request/response shapes preserved
- [ ] Async/event timing preserved: no change to when async work or events fire relative to transaction commit
- [ ] Profile behavior preserved: refactored code works the same across all active profiles

---

## 6. Verification Rules

To verify Spring code correctness:
- [ ] Call-path review: for any `@Transactional`/`@Cacheable`/`@Async` method, verify the call passes through a Spring proxy
- [ ] Transaction scenario: test commit path AND rollback path (force an exception)
- [ ] Bean wiring: `@SpringBootTest` with all beans loaded — no startup errors
- [ ] Configuration: test with production profile/values
- [ ] Controller: `@WebMvcTest` or integration test with actual JSON request/response
- [ ] Cross-module: verify dependent module beans are in the container (startup test)
