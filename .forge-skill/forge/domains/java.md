# Domain: Java

## 1. Activation

Load this domain when the task involves `.java` files, Java classes/interfaces/records/enums, JVM-based services, or Java language semantics.

**Auto-detect signals**: `.java` file extension, `import java`, `package` declarations, Java annotations, Java exception types in stack traces, JVM options.

---

## 2. Review Checklist

When reviewing Java code, verify each item. Mark N/A if not applicable.

### 2.1 Null Safety
- [ ] Every method parameter: is null handled or explicitly rejected?
- [ ] Methods returning null: is the null meaning documented? Would `Optional` be clearer?
- [ ] Chained dereferences (`a.b().c()`): can any intermediate value be null?
- [ ] Collection/array returns: null vs empty — is the contract consistent?
- [ ] `@Nullable` / `@NonNull` annotations: do they match actual behavior?

### 2.2 Exception Handling
- [ ] No empty catch blocks (swallowed exceptions)
- [ ] Catch blocks are specific (`catch (IOException)` not `catch (Exception)`)
- [ ] Exception translation preserves the original exception as cause
- [ ] Checked exceptions: are they genuinely recoverable? If not, should they be unchecked?
- [ ] Finally blocks: are they exception-safe (no resource ops that can throw)?
- [ ] Error codes vs exceptions: is the choice intentional?

### 2.3 Collections and Generics
- [ ] Raw types eliminated — all generic types are parameterized
- [ ] Collections returned from methods: are they defensively copied or immutable?
- [ ] Stream operations: no side effects hidden inside `map`/`filter`/`peek`
- [ ] Complex stream chains: would a loop be clearer?
- [ ] `parallelStream()`: is it justified by data size? Is thread safety guaranteed?
- [ ] Collection choice: `ArrayList` vs `LinkedList` vs `HashSet` vs `TreeSet` — is it appropriate?

### 2.4 Concurrency
- [ ] Shared mutable state: is it protected by synchronization, volatile, or atomic classes?
- [ ] Non-thread-safe collections (`HashMap`, `ArrayList`): are they ever accessed from multiple threads?
- [ ] Check-then-act sequences: are they atomic?
- [ ] Lazy initialization: is it thread-safe (double-checked locking correct, or holder pattern)?
- [ ] `volatile` fields: is the happens-before guarantee sufficient for the use case?
- [ ] Thread pools / executors: are they shut down properly?

### 2.5 Equality and Hashing
- [ ] `equals()` and `hashCode()`: both overridden together
- [ ] Mutable fields used in `equals`/`hashCode`? (will break in hash collections)
- [ ] Entity equality: ID-based or field-based? Is it consistent with JPA requirements?
- [ ] `Comparable` implementation: consistent with `equals`?

### 2.6 Resource Management
- [ ] All `Closeable`/`AutoCloseable` resources use try-with-resources
- [ ] Streams, connections, files: closed in all paths (normal + exception)
- [ ] Resource ownership: is it clear who is responsible for closing?
- [ ] No resource fields in long-lived objects without explicit lifecycle management

### 2.7 API Design
- [ ] Public API surface: minimal, intentional
- [ ] Method contracts clear: what are preconditions, postconditions, side effects?
- [ ] Boolean flag parameters: would an enum be clearer?
- [ ] "God" classes: single responsibility or too many concerns?
- [ ] Internal state exposed: are defensive copies needed?
- [ ] Naming: does the name accurately describe behavior?

### 2.8 JVM-Level Concerns
- [ ] Static initializers: are they simple and fail-fast? (complex static init can deadlock)
- [ ] `finalize()`: avoid it — use `Cleaner` or try-with-resources instead
- [ ] Class loading assumptions: any reliance on specific class loading order?
- [ ] Native methods: are they necessary? Are failure modes handled?

---

## 3. Debug Heuristics

### Pattern: NullPointerException
- **Symptom**: `NullPointerException` at a specific line
- **Common causes**: Missing null check, uninitialized field, Optional misuse, autoboxing of null, async completion returning null
- **Diagnose**: Trace the null value back to its origin. Is it a parameter? A field? A method return? Was it set at the right time?
- **Fix**: If legitimate absence → `Optional`; if invariant violation → fail-fast with clear message; if oversight → add null guard

### Pattern: ClassCastException
- **Symptom**: `ClassCastException` — "X cannot be cast to Y"
- **Common causes**: Generic type erasure, incorrect DI wiring, deserialization producing wrong type, raw type usage
- **Diagnose**: Find where the object was created and what type it actually is. Check for unchecked casts.
- **Fix**: Fix the source of the wrong type; suppress warnings only with documented justification

### Pattern: ConcurrentModificationException
- **Symptom**: `ConcurrentModificationException` during iteration
- **Common causes**: Modifying a collection while iterating (same thread), or concurrent access without synchronization
- **Diagnose**: Identify all threads touching the collection. Check for hidden modifications inside callbacks.
- **Fix**: Use `CopyOnWriteArrayList`, `ConcurrentHashMap`, or iterate over a snapshot

### Pattern: OutOfMemoryError
- **Symptom**: OOM — Java heap space, Metaspace, or GC overhead limit
- **Common causes**: Memory leak (unclosed resources, growing static caches, ThreadLocal accumulation), insufficient -Xmx, excessive class loading (dynamic proxies, lambda metafactory)
- **Diagnose**: Heap dump analysis. Top consumers by retained size. GC log analysis.
- **Fix**: Fix the leak; increase heap only if usage is legitimate

### Pattern: Deadlock
- **Symptom**: Application hangs, threads in BLOCKED state
- **Common causes**: Inconsistent lock ordering, nested synchronized blocks, database + JVM lock interaction
- **Diagnose**: Thread dump — find threads in BLOCKED, trace lock holders
- **Fix**: Consistent lock ordering, `java.util.concurrent.locks` with timeouts, reduce synchronized scope

---

## 4. Error Patterns

| Error | Layer | Meaning | Fix Direction |
|-------|-------|---------|---------------|
| `NullPointerException` | App | Null dereference at call site | Add null guard or Optional |
| `IllegalArgumentException` | App | Invalid argument passed to method | Validate at entry, document contract |
| `IllegalStateException` | App | Object in wrong state for operation | Check state machine, add precondition |
| `ClassCastException` | App | Wrong type assumption | Fix type source, avoid unchecked casts |
| `IndexOutOfBoundsException` | App | Collection/array access beyond bounds | Guard with size check |
| `ConcurrentModificationException` | App | Unsafe concurrent collection access | Use concurrent collection or synchronize |
| `NoClassDefFoundError` | JVM | Class present at compile time, missing at runtime | Fix dependency scope, check classpath |
| `NoSuchMethodError` | JVM | Method signature mismatch at runtime | Check dependency version compatibility |
| `OutOfMemoryError: Java heap` | JVM | Heap exhausted | Fix leak or increase -Xmx |
| `OutOfMemoryError: Metaspace` | JVM | Class metadata area exhausted | Check for ClassLoader leak, increase -XX:MaxMetaspaceSize |
| `StackOverflowError` | JVM | Infinite recursion or deep call chain | Fix recursion termination, convert to loop |
| `ClassNotFoundException` | JVM | Dynamic class loading failed | Check class name, verify dependency |

---

## 5. Refactor Guidelines

When refactoring Java code, verify:
- [ ] Behavior preserved: same inputs produce same outputs and side effects
- [ ] `equals`/`hashCode` contract preserved after field changes
- [ ] Serialization compatibility: `serialVersionUID` explicit if class is serializable
- [ ] Thread safety not degraded: if class was thread-safe, it stays thread-safe
- [ ] Public API unchanged: unless intentionally evolving, signatures stay compatible
- [ ] Resource lifecycle unchanged: close timing and ownership preserved
- [ ] Extracted methods: exception behavior preserved (checked exceptions declared)
- [ ] Generics: no raw type warnings introduced; type safety maintained

---

## 6. Verification Rules

To verify Java code correctness:
- [ ] Edge-case walkthrough: null input, empty collections, boundary values, concurrent access
- [ ] Exception path: force each failure mode and verify behavior
- [ ] Equality: unit test for symmetric, transitive, consistent with equals/hashCode
- [ ] Resource leak: review all Closeable paths; static analysis if available
- [ ] Thread safety: concurrent test with multiple threads; or documented as not thread-safe
- [ ] API contract: parameter validation tested; return value documented and tested
