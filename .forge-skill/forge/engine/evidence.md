# Engine: Evidence

## Purpose

Evidence is the stage where observations are gathered, separated, and organized before interpretation.

Its purpose is to create a reliable factual base for later reasoning.

Evidence prevents:
- speculation disguised as analysis
- conclusions unsupported by artifacts
- confusion between symptoms and causes
- loss of traceability
- overconfidence based on weak signals

No serious reasoning should occur without some evidence discipline.

---

## Core Objective

Convert available artifacts into structured observations while preserving source fidelity.

A strong Evidence stage should answer:

- What do we actually know?
- Where does each fact come from?
- Which observations are direct versus inferred?
- What data is missing?
- Which signals are strong, weak, or conflicting?

---

## Inputs

Typical evidence sources include:

- source code
- configuration files
- test code
- test output
- logs
- stack traces
- SQL queries
- runtime metrics
- diffs
- commit messages
- error messages
- screenshots
- user-provided scenarios
- repository structure

Evidence may be:
- complete or partial
- current or stale
- direct or indirect
- reliable or noisy

The Evidence stage should preserve these distinctions.

---

## Outputs

The Evidence stage should produce:

- evidence inventory
- observation list
- assumption list
- contradiction list if needed
- evidence gaps
- confidence notes on evidence quality

A strong output makes later reasoning auditable.

---

## Evidence Principles

### 1. Observe before explaining
Record what is present before deciding what it means.

### 2. Preserve source specificity
Whenever possible, keep the exact source:
- file and function
- log line
- test name
- stack frame
- config key
- user quote

### 3. Distinguish direct evidence from inference
Example:
- direct: a method catches `Exception` and returns null
- inference: this may hide production failures

The first belongs to Evidence.
The second belongs to Reasoning.

### 4. Prefer primary sources
Prefer actual artifacts over summaries of artifacts.

### 5. Record contradictions honestly
If two signals conflict, keep both visible.

---

## Evidence Categories

### Direct code evidence
Examples:
- method logic
- control flow
- null checks
- transaction annotations
- cache TTL settings
- query shape
- retries or exception handling

### Runtime evidence
Examples:
- logs
- stack traces
- timeouts
- HTTP responses
- retry behavior
- memory or CPU observations

### Test evidence
Examples:
- failing tests
- passing tests
- missing assertions
- flaky behavior
- scenario coverage

### Configuration evidence
Examples:
- environment variables
- Spring properties
- Redis configuration
- connection pool sizing
- timeout values

### Structural evidence
Examples:
- package boundaries
- module dependencies
- naming conventions
- file placement
- layering patterns

### User-reported evidence
Examples:
- "fails only in CI"
- "happens after deployment"
- "started after this change"
- "works locally but not in staging"

User reports are evidence, but often lower precision until corroborated.

---

## Evidence Data Model

For each meaningful evidence item, capture:

- source
- observation
- type
- relevance
- strength
- confidence
- notes

### Example
- source: `OrderService.java`, method `createOrder`
- observation: method writes DB state before external payment confirmation
- type: direct code evidence
- relevance: high
- strength: high
- confidence: high
- notes: potential consistency risk if payment fails after persistence

---

## Evidence Collection Process

### Step 1: Inventory available artifacts
List what is actually available now.

Example:
- one service class
- one repository
- one stack trace
- one failing Playwright test
- no production logs

### Step 2: Extract direct observations
Capture what can be seen directly without interpretation.

Example:
- method retries external API call three times
- Redis key uses a fixed 24h TTL
- test uses `waitForTimeout(5000)`

### Step 3: Tag source and confidence
Record where each observation came from and how reliable it is.

### Step 4: Identify missing evidence
Examples:
- no query plan
- no failing input
- no surrounding transaction config
- no thread model context

### Step 5: Identify contradictions
Examples:
- logs suggest timeout, code suggests immediate validation failure
- user says issue is intermittent, test failure is deterministic
- annotation suggests transaction, but actual call path may bypass proxy

### Step 6: Prepare evidence for reasoning
Organize evidence so downstream reasoning can compare and rank interpretations.

---

## Strong vs Weak Evidence

### Strong evidence
- exact code path
- exact failing stack trace
- exact config values
- exact query or test behavior
- exact reproduction sequence
- concrete before/after diff

### Medium evidence
- repository structure strongly implying framework usage
- user reports consistent with code and logs
- framework conventions likely but not directly confirmed

### Weak evidence
- inference based on naming alone
- assumptions about deployment topology
- generic "this framework usually behaves like..."
- outdated screenshots without timestamps or context

Weak evidence may inform hypotheses, but should not anchor high-confidence conclusions.

---

## Evidence Handling Rules by Situation

### Code review situation
Collect:
- exact code path
- explicit contracts
- edge-case handling
- exception behavior
- side effects
- test coverage signals

### Debug situation
Collect:
- symptom artifacts
- failing conditions
- exact error path
- recent changes if available
- environmental differences
- reproduction evidence

### Refactor situation
Collect:
- duplication
- coupling
- complexity hot spots
- public contracts
- tests protecting behavior

### Optimization situation
Collect:
- bottleneck signals
- query shape
- allocation patterns
- repeated work
- latency indicators
- baseline metrics if available

---

## Evidence Formatting Guidance

When surfacing evidence in outputs, prefer forms like:

- "In `UserCacheService#getUser`, the cache key omits tenant ID."
- "The test uses `waitForTimeout(3000)`, which creates timing-based flakiness."
- "The stack trace shows failure in the proxy invocation layer before repository execution."
- "No assertion verifies the side effect after the HTTP request."

Avoid vague phrasing like:
- "There may be a problem somewhere in the cache logic."
- "This seems risky."
- "The code is probably doing too much."

---

## Evidence Gap Management

Evidence is often incomplete.
The goal is not perfect completeness; it is explicit incompleteness.

For each gap, determine:

- is this gap blocking?
- does it lower confidence only?
- can reasoning continue with bounded assumptions?
- should the user be asked for more data now or later?

### Example
Missing:
- production config for cache TTL
Impact:
- prevents strong claims about real expiry behavior
Action:
- proceed with code-level review, label deployment-specific uncertainty

---

## Contradiction Handling

Contradictions are valuable signals.

### Types of contradictions
- code contradicts user expectation
- logs contradict current hypothesis
- config contradicts assumed runtime behavior
- tests imply one contract, implementation another

### Handling rule
Do not hide contradictions to keep the narrative clean.
Instead:
- record them
- use them to lower confidence
- let them shape hypotheses

---

## Evidence Anti-Patterns

### Anti-pattern 1: interpretation disguised as evidence
Bad:
- "This method is buggy"
Good:
- "This method catches all exceptions and returns success=false without propagating details"

### Anti-pattern 2: weak evidence treated as certain
Bad:
- "This is definitely a proxy issue"
Good:
- "The stack trace includes proxy invocation layers, suggesting proxy behavior may be involved"

### Anti-pattern 3: source loss
Bad:
- "The config is wrong"
Good:
- "`application.yml` sets `spring.transaction.default-timeout=1`, which may be too low for this flow"

### Anti-pattern 4: selective evidence
Ignoring artifacts that complicate the current theory.

---

## Evidence Completion Criteria

Evidence is sufficient to move forward when:

1. the available artifacts are inventoried
2. direct observations are captured
3. important sources are traceable
4. assumptions are distinguishable from facts
5. material evidence gaps are identified
6. contradictions are noted if present

Reasoning may begin once this threshold is met.

---

## Short Reminder

Before moving to Context or Reasoning, ensure:
- observations are direct
- sources are preserved
- evidence strength is understood
- assumptions are separated
- important gaps are visible
