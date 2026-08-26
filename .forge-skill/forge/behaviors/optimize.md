# Behavior: Optimize

## Purpose

Optimize behavior is used when the task is to improve performance, efficiency, scalability, or resource usage.

Optimization may target:
- latency
- throughput
- memory usage
- CPU cost
- database load
- network overhead
- cache efficiency
- execution stability under scale
- operational cost

Optimize should help the user answer:
- what is likely expensive or slow
- why it is expensive or slow
- what change would have the highest payoff
- what tradeoffs that change introduces
- how the improvement should be validated

Optimization is not only about speed.
It is about justified efficiency improvement under real constraints.

---

## Activation Signals

Activate optimize behavior when the primary task is to improve performance, efficiency, or resource cost.

### Typical user request signals
- optimize this
- this is slow
- improve performance
- reduce latency
- too many queries
- high CPU usage
- memory issue
- improve throughput
- reduce cost
- make this more efficient

### Typical task shapes
- slow query investigation
- hot path optimization
- repeated I/O reduction
- cache efficiency improvement
- flaky performance under load
- resource-heavy data processing
- expensive browser or test execution path

### Typical artifact signals
- slow endpoint
- large-tenant slowdown
- repeated DB lookups
- excessive allocations
- broad locking or contention
- miss-heavy cache flow
- repeated waits or polling
- N+1 access patterns
- high-cost loop or transformation path

### Boundary reminder
Use optimize when the primary need is efficiency improvement.

Do not use optimize as the primary behavior when the user's main need is:
- broad quality review
- root-cause diagnosis without performance intent
- structural cleanup without efficiency goal
- concept explanation

Optimization can include diagnosis and review thinking, but it should remain anchored in cost, bottlenecks, and measurable impact.

---

## Core Mindset

Optimize with the mindset of justified efficiency improvement.

That means:

- find the bottleneck before proposing major changes
- prefer evidence over intuition
- preserve correctness
- prefer large wins over clever micro-optimizations
- measure or define what success means
- explain tradeoffs honestly
- avoid complexity that costs more than it saves

A good optimization result is not "this looks faster."
It is "this change is likely to improve the right bottleneck, for clear reasons, with acceptable tradeoffs."

---

## Primary Priorities

In most optimization tasks, prioritize roughly in this order:

1. identify or validate the likely bottleneck
2. preserve correctness
3. target the highest-impact opportunity
4. minimize complexity increase
5. explain tradeoffs
6. define measurable validation
7. avoid premature optimization

This order matters.
A technically clever optimization that solves the wrong problem is not good optimization work.

---

## Optimize Responsibilities

### 1. Identify the likely cost center
Examples:
- slow SQL query
- repeated network calls
- repeated object construction
- expensive serialization
- lock contention
- cache miss amplification
- browser timing waste
- repeated file or API access in loops

Optimization should first identify what seems expensive.

### 2. Distinguish actual bottleneck from suspicious code
Some code looks inefficient but does not matter in practice.
Some code looks harmless but dominates cost under scale.

Optimization should ask:
- does this run often?
- does this run on the hot path?
- does this scale poorly?
- does this trigger expensive external work?

### 3. Estimate payoff direction
When exact measurement is unavailable, optimization should still explain why a change is expected to help.

Examples:
- fewer DB round trips
- reduced serialization cost
- smaller lock duration
- better index alignment
- fewer repeated renders
- fewer cache misses under traffic

### 4. Protect correctness
Optimization must not silently change:
- semantics
- freshness guarantees
- ordering guarantees
- concurrency assumptions
- transaction behavior
- user-visible behavior

A fast wrong answer is still wrong.

### 5. Define verification strategy
Optimization should not end with "should be better."
It should define:
- what metric should improve
- what evidence would support success
- what regression risk should be checked

---

## Optimize Questions

Use these internally while optimizing.

### Bottleneck questions
- What work is most likely expensive?
- What repeats unnecessarily?
- Is cost dominated by CPU, I/O, memory, locking, network, rendering, or waiting?
- Is this path hot enough to matter?

### Access pattern questions
- Are there repeated lookups or calls in loops?
- Are we doing more data loading than needed?
- Are we paying cost before filtering or narrowing?

### Tradeoff questions
- What complexity does this introduce?
- Does it make the code harder to verify or maintain?
- Is the payoff likely worth the added complexity?

### Correctness questions
- Could this change ordering, consistency, or behavior?
- Does it introduce stale data risk, race risk, or reduced precision?
- Is there a hidden contract that optimization could break?

### Validation questions
- What metric should improve?
- What baseline matters?
- What outcome would show failure of the optimization hypothesis?

---

## Typical Optimization Targets

Common high-value optimization targets include:

- repeated database round trips
- N+1 query patterns
- unnecessary remote calls
- expensive per-item processing in large loops
- broad cache invalidation causing churn
- over-broad locking
- unnecessary object creation or copying
- full scans caused by poor query/index alignment
- repeated rendering or waiting in browser tests
- over-fetching and post-filtering large result sets
- duplicated expensive calculations

These are often better targets than micro-level syntax changes.

---

## What Optimize Should Prefer

Prefer:
- bottleneck-first reasoning
- the simplest high-impact fix
- changes that reduce repeated expensive work
- changes with clear validation paths
- changes that preserve maintainability where possible
- staged optimization when risk is non-trivial

Prefer statements like:
- "This likely creates N+1 DB access because..."
- "The index order does not match the filter/order pattern..."
- "This caching approach reduces reads, but introduces invalidation complexity..."
- "The current wait strategy wastes time on the happy path and still remains flaky under slower conditions..."

---

## What Optimize Should Avoid

Avoid:
- speculative micro-optimizations
- changing many things without knowing what matters
- sacrificing correctness for speed
- introducing caches without invalidation discipline
- shifting cost elsewhere without acknowledging it
- claiming performance gains without defining what should improve
- using "faster" as a vague aesthetic label

Bad:
- "Use a cache."

Better:
- "If this endpoint repeatedly reads the same data and tolerates bounded staleness, a cache could reduce DB load. The design must define invalidation and stale-read tolerance explicitly."

Bad:
- "Use streams less."

Better:
- "This pipeline materializes intermediate collections repeatedly inside a hot loop, which likely adds allocation and traversal cost under larger input sizes."

---

## Local vs Systemic Optimization

Optimization should distinguish:

### Local optimization
Improves one method, query, or step.

### Path optimization
Improves an end-to-end request or workflow path.

### Systemic optimization
Changes a broader access pattern, caching model, batching strategy, or architectural behavior.

This matters because:
- risk differs
- verification differs
- payoff differs
- rollout complexity differs

A local optimization is usually easier to justify and verify.
A systemic optimization may be more powerful, but also riskier.

---

## Optimization Under Limited Metrics

Sometimes no profiler, benchmark, or representative production metric is available.

In that case:
- use structural evidence carefully
- explain the expected gain qualitatively
- lower confidence
- recommend the next best measurement

Example:
"This query shape likely causes poor index use because the predicate wraps the indexed column in a function. Confidence is medium without an execution plan; validate with `EXPLAIN` on representative data."

Optimization without precise metrics is still possible, but it must be more explicit about uncertainty.

---

## Cost-Shifting Awareness

A strong optimizer checks whether an improvement in one layer creates cost elsewhere.

Examples:
- adding cache reduces DB load but increases invalidation complexity
- batching reduces round trips but increases peak memory
- precomputation improves reads but slows writes
- tighter waits speed local runs but reduce failure diagnosability if overdone
- lock reduction may increase eventual consistency complexity

Optimization should surface these tradeoffs instead of pretending there is only upside.

---

## Validation Guidance

Optimization validation should answer:

- what metric should improve
- what baseline is relevant
- what scenario matters
- what correctness risks must still be checked

Possible validation methods:
- query count comparison
- `EXPLAIN` plan review
- before/after latency comparison
- throughput comparison
- allocation or CPU profile review
- repeated CI test runtime analysis
- lock/contention observation
- cache hit/miss or stale-read behavior review

---

## Optimization Anti-Patterns

### Anti-pattern 1: premature optimization
Improving low-impact code before validating importance.

### Anti-pattern 2: hotspot guesswork
Optimizing what looks suspicious rather than what evidence suggests is expensive.

### Anti-pattern 3: metric-free success claims
Saying something is optimized without defining what improved.

### Anti-pattern 4: correctness regression
Breaking semantics, consistency, or behavior under the banner of speed.

### Anti-pattern 5: complexity blindness
Ignoring long-term cost of maintaining the optimization.

### Anti-pattern 6: local-only thinking
Reducing cost in one place while increasing it elsewhere without acknowledging it.

### Anti-pattern 7: optimization by folklore
Applying generic performance advice without local justification.

---

## Optimize Completion Criteria

An optimization result is strong when it can answer:

1. what the likely bottleneck or cost center is
2. what evidence supports that belief
3. what change is recommended
4. why that change should help
5. what tradeoffs it introduces
6. how success should be validated
7. what correctness or operational risks remain

---

## Short Reminder

When optimize is active:
- identify the real bottleneck first
- preserve correctness
- prefer large justified wins
- explain tradeoffs
- define how success will be measured
