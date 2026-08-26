# Engine: Verification

## Purpose

Verification checks whether the result actually satisfies the intended goal.

It is the stage that distinguishes:
- plausible from confirmed
- changed from improved
- patched from validated
- analyzed from trusted

Verification exists to prevent:
- false confidence
- untested fixes
- silent regressions
- unsupported claims of success
- incomplete closure on high-impact tasks

Verification should be proportional, explicit, and honest.

---

## Core Objective

Determine what has been confirmed, what remains uncertain, and how much confidence is justified.

A strong Verification stage should answer:

- What was checked?
- How was it checked?
- What passed?
- What remains unverified?
- What residual risks remain?
- How confident should we be in the result?

---

## Inputs

Verification uses:

- task objective
- plan and intended success criteria
- execution outputs
- available tests
- available reasoning checks
- observed outcomes
- known constraints and risk areas

Verification may be:
- dynamic
- static
- conceptual
- partial
- staged

---

## Outputs

Verification should produce:

- verification summary
- methods used
- confirmed outcomes
- unverified areas
- residual risks
- confidence statement
- follow-up validation recommendations if needed

---

## Verification Responsibilities

### 1. Check against the original objective
Do not verify abstract quality alone.
Verify whether the intended task outcome was achieved.

### 2. Confirm important claims
Examples:
- bug is fixed
- logic is now correct
- test is less flaky
- refactor preserved behavior
- query is more efficient
- document reflects actual behavior

### 3. Look for regressions
A local fix may introduce a broader problem.
Verification should examine likely risk areas.

### 4. Report partial verification honestly
If only static review was possible, say so.
If no runtime test was available, say so.
If verification depends on deployment context, say so.

### 5. Calibrate confidence
Confidence should emerge from what was actually verified.

---

## Verification Methods

### 1. Test-based verification
Examples:
- unit tests
- integration tests
- e2e tests
- regression tests
- contract tests

### 2. Static verification
Examples:
- code path review
- type consistency review
- logic walkthrough
- edge-case analysis
- query/index reasoning

### 3. Scenario verification
Examples:
- expected input/output walkthrough
- failure-path walkthrough
- concurrency scenario review
- cache invalidation sequence review

### 4. Operational verification
Examples:
- metrics review
- log confirmation
- alert behavior
- rollout observation
- performance measurement

### 5. Documentation verification
Examples:
- consistency with implementation
- audience completeness
- examples matching actual behavior

Different tasks justify different combinations.

---

## Verification Process

### Step 1: Restate success criteria
Identify what "worked" means for this task.

### Step 2: Select appropriate methods
Use methods proportional to:
- risk
- change surface
- available artifacts
- task type

### Step 3: Check primary objective
Confirm whether the core issue was addressed.

### Step 4: Check high-risk side effects
Review likely regression areas.

### Step 5: Report confirmed vs unconfirmed
Separate:
- verified
- likely but not verified
- not verified
- blocked from verification

---

## Verification by Behavior

### Review behavior
Verification may focus on:
- whether findings are evidence-supported
- whether severity is justified
- whether proposed fixes are coherent

### Debug behavior
Verification focuses on:
- whether root cause is actually confirmed
- whether the fix addresses the failure mechanism
- whether competing hypotheses are sufficiently ruled out

### Refactor behavior
Verification focuses on:
- preserved external behavior
- unchanged contracts
- reduced complexity without regression
- adequate test safety

### Optimize behavior
Verification focuses on:
- measurable gain
- no correctness regression
- acceptable complexity tradeoff

### Document behavior
Verification focuses on:
- accuracy
- completeness for audience
- alignment with actual system behavior

### Explain behavior
Verification focuses on:
- correctness
- conceptual clarity
- example validity

---

## Verification Depth Levels

### Lightweight verification
Used for:
- small low-risk suggestions
- conceptual explanation
- non-invasive review comments

Examples:
- logic walkthrough
- local consistency check

### Moderate verification
Used for:
- bug fixes
- local refactors
- test changes
- query improvements

Examples:
- targeted tests
- edge-case review
- scenario analysis

### Strong verification
Used for:
- production incident fixes
- concurrency-sensitive changes
- transaction or consistency changes
- distributed behavior changes
- performance-critical changes

Examples:
- multi-scenario testing
- regression-focused review
- metrics or rollout monitoring
- failure-path validation

---

## Partial Verification Rules

Partial verification is normal.
Unacknowledged partial verification is not.

When verification is incomplete, specify:

- what was verified
- what could not be verified
- why it could not be verified
- what risk remains because of that gap
- what next validation step is recommended

### Example
"Static review supports the fix for duplicate cache population, but concurrency behavior was not runtime-verified because no reproduction harness was available."

That is far stronger than simply saying "looks good."

---

## Residual Risk Analysis

Verification should identify what may still fail even if the main task succeeded.

Examples:
- bug fixed for one code path but not all call sites
- transaction fix still depends on external API latency
- Playwright test stabilized locally but CI resource contention remains possible
- query improved but index creation has migration risk

Residual risk is not a sign of weak work; hiding it is.

---

## Verification Anti-Patterns

### Anti-pattern 1: success by intuition
Declaring success because the change seems reasonable.

### Anti-pattern 2: verification without objective
Checking random things without tying them to task goals.

### Anti-pattern 3: no distinction between tested and assumed
Blurring what actually passed with what merely appears likely.

### Anti-pattern 4: regression blindness
Verifying the target fix only, ignoring likely collateral impact.

### Anti-pattern 5: overstated confidence
Using strong certainty labels without corresponding checks.

### Anti-pattern 6: checklist theater
Listing tests or checks without explaining what they validated.

---

## Verification Completion Criteria

Verification is sufficient when the assistant can state:

1. what success criteria were used
2. what verification method was applied
3. what is confirmed
4. what is not confirmed
5. what risks remain
6. how much confidence is justified

If these are unclear, verification is incomplete.

---

## Short Reminder

Before moving to Delivery, ensure:
- claims of success are grounded
- verified and unverified areas are separated
- residual risks are visible
- confidence is calibrated
- follow-up validation is suggested where needed
