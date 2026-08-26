# Engine: Context

## Purpose

Context places evidence inside the system conditions that give it meaning.

A line of code, a log entry, or a failing test cannot be judged correctly in isolation if surrounding constraints are unknown.
Context exists to answer:
- where this behavior lives
- what conditions shape it
- what dependencies influence it
- what tradeoffs or operating assumptions apply

Context prevents:
- technically correct but situationally wrong conclusions
- framework misunderstandings
- ignoring environmental constraints
- overgeneralizing from local evidence

---

## Core Objective

Build a working model of the environment around the evidence.

A strong Context stage should answer:

- What kind of system is this?
- What runtime or framework assumptions matter?
- What neighboring components influence the observed behavior?
- What operational or business constraints shape acceptable solutions?
- What hidden boundaries or contracts matter?

---

## Inputs

Context is derived from:

- evidence gathered earlier
- repository structure
- dependency and framework signals
- naming and layering conventions
- architecture hints
- environment references
- deployment assumptions if known
- user-provided system description
- domain modules relevant to the task

Context may be:
- explicit
- implicit
- partially inferred
- uncertain

Those distinctions must remain visible.

---

## Outputs

The Context stage should produce:

- context summary
- system model notes
- runtime assumptions
- dependency map
- operational constraints
- contract assumptions
- contextual risks
- unresolved context gaps

This output should help reasoning avoid decontextualized judgment.

---

## Context Dimensions

### 1. Technical stack context
Examples:
- Java service
- Spring Boot application
- Redis-backed cache
- MySQL persistence layer
- Playwright end-to-end test environment

### 2. Runtime context
Examples:
- synchronous request flow
- async worker
- retry-driven integration
- transactional boundary
- distributed cache interaction
- CI-only test runtime

### 3. Architectural context
Examples:
- controller -> service -> repository layering
- event-driven workflow
- external API dependency
- cache-aside pattern
- read/write path separation

### 4. Operational context
Examples:
- production sensitivity
- low-latency requirement
- high concurrency
- rollout constraints
- backward compatibility
- partial failure tolerance

### 5. Contract context
Examples:
- method behavior expectations
- API response guarantees
- idempotency expectations
- transaction guarantees
- cache consistency model
- test determinism expectations

### 6. Team or repository context
Examples:
- strong annotation conventions
- common utility patterns
- package organization norms
- preferred testing style
- migration safety practices

---

## Context Responsibilities

### 1. Situate the artifact
Determine where the artifact sits in the larger system.

Example:
A service method may not be a simple local function.
It may be:
- inside a transaction proxy
- called by a controller
- writing to MySQL
- publishing an event
- updating Redis
- participating in retries

### 2. Recover hidden assumptions
A lot of software behavior is shaped by assumptions not visible in a single snippet.

Examples:
- Spring proxy-based transactions
- lazy loading behavior
- Redis eventual consistency tolerance
- Playwright timing sensitivity in CI
- database isolation semantics

### 3. Identify relevant constraints
Not every valid fix is acceptable.
Context should reveal constraints like:
- cannot break API contract
- must preserve event ordering
- must avoid long transactions
- must support retries
- test must remain deterministic in CI

### 4. Distinguish local issue from systemic pattern
A problem may be:
- isolated
- repeated
- architectural
- framework-induced
- operational rather than code-local

### 5. Surface risk-bearing boundaries
Boundaries often amplify risk:
- service <-> repository
- application <-> external API
- cache <-> database
- test <-> browser timing
- transaction <-> async execution

---

## Context Construction Process

### Step 1: Identify the technical environment
Determine likely languages, frameworks, and infrastructure involved.

### Step 2: Identify execution environment
Ask:
- where does this code run?
- under what lifecycle?
- under what load or timing assumptions?
- in what environment does the failure appear?

### Step 3: Identify neighboring components
Determine:
- who calls this
- what it depends on
- what state it mutates
- what external systems it touches

### Step 4: Identify constraints and tradeoffs
Examples:
- latency vs consistency
- readability vs abstraction
- test speed vs reliability
- short transactions vs cross-system coordination

### Step 5: Identify contextual unknowns
Examples:
- actual transaction propagation path unknown
- deployment topology unknown
- cache invalidation strategy incomplete
- CI parallelism not shown

---

## Context Questions

Use these questions internally.

### System questions
- What kind of system is this?
- What framework behavior is likely involved?
- Is this local code or part of a larger distributed flow?

### Runtime questions
- Is the code executed synchronously or asynchronously?
- Under what environment does the issue occur?
- Are retries, timeouts, locks, or transactions involved?

### Dependency questions
- What upstream and downstream components matter?
- What external system behavior could shape the result?
- Does this artifact rely on proxying, configuration, or hidden lifecycle behavior?

### Constraint questions
- What must not change?
- What non-functional expectations matter?
- Is consistency, throughput, latency, or simplicity the dominant constraint?

### Contract questions
- What behavior do callers likely expect?
- Are there explicit or implicit invariants?
- Is the code idempotent, transactional, or eventually consistent by design?

---

## Context Patterns by Domain

### Java context patterns
- object lifecycle
- exception propagation
- thread safety
- mutability assumptions
- API contracts

### Spring context patterns
- bean lifecycle
- proxy-based behavior
- transaction boundaries
- request vs singleton scope
- validation and serialization paths
- configuration-driven behavior

### Redis context patterns
- cache-aside or write-through strategy
- TTL behavior
- cache invalidation timing
- race conditions under concurrency
- stale read tolerance

### MySQL context patterns
- transaction isolation
- locking behavior
- query/index relationship
- pagination semantics
- consistency during concurrent writes

### Playwright context patterns
- browser timing
- locator stability
- fixture isolation
- CI environment variability
- retry semantics

### Testing context patterns
- deterministic assertions
- state isolation
- mock realism
- test pyramid fit
- failure diagnosability

---

## Local vs Systemic Distinction

Context should ask whether an issue is:

### Local
Confined to one method, class, or query.

### Cross-cutting
Spread across multiple layers or repeated patterns.

### Emergent
Caused by interactions rather than a single flawed line.

### Environmental
Appearing only under specific deployment, CI, concurrency, or configuration conditions.

This distinction matters because it changes:
- severity
- fix strategy
- verification approach
- rollout risk

---

## Context Anti-Patterns

### Anti-pattern 1: snippet isolation
Judging a snippet as though it were the entire system.

### Anti-pattern 2: generic framework assumptions
Assuming framework behavior without local confirmation.

### Anti-pattern 3: ignoring operating constraints
Suggesting elegant solutions that violate throughput, compatibility, or deployment needs.

### Anti-pattern 4: missing boundary effects
Failing to notice that correctness depends on interactions with another system.

### Anti-pattern 5: overstating inferred context
Treating guessed architecture as confirmed fact.

---

## Context Completion Criteria

Context is sufficient when the assistant can describe:

1. what kind of system this is
2. what runtime conditions matter
3. what neighboring components or dependencies are relevant
4. what constraints shape acceptable conclusions or changes
5. what contextual uncertainties still limit confidence

Perfect completeness is not required.
Useful situated understanding is required.

---

## Short Reminder

Before moving fully into Reasoning, ensure:
- evidence is situated
- framework/runtime assumptions are visible
- dependencies are recognized
- constraints are explicit
- contextual uncertainty is acknowledged
