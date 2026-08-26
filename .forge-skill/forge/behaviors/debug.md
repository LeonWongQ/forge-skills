# Behavior: Debug

## Purpose

Debug behavior is used when the task is to identify, isolate, explain, and validate the cause of a failure or unexpected behavior.

Debugging is not merely searching for suspicious code.
It is disciplined uncertainty reduction.

Debug focuses on:
- symptom definition
- reproduction conditions
- evidence collection
- hypothesis management
- root-cause identification
- corrective action validation

Debug should help the user answer:
- what is failing
- why it is failing
- what evidence supports that explanation
- what fix is most justified
- how to confirm the fix

---

## Activation Signals

Activate debug behavior when the primary task is to explain or isolate failure, unexpected behavior, or instability.

### Typical user request signals
- debug this
- why is this failing?
- find the root cause
- investigate this error
- diagnose this issue
- why does this only fail in CI?
- what is causing this?
- help me reproduce this bug

### Typical task shapes
- runtime failure investigation
- flaky test diagnosis
- transaction issue diagnosis
- stale data investigation
- integration failure analysis
- regression investigation
- environment-specific failure analysis

### Typical artifact signals
- stack trace
- logs
- failing test output
- error screenshot
- inconsistent runtime behavior
- reproduction steps
- "works locally but fails in staging/CI" description

### Boundary reminder
Use debug when the primary need is causal understanding.

Do not use debug as the primary behavior when the user's main need is:
- broad quality review
- conceptual explanation
- structural cleanup
- pure implementation planning

Debug may produce fix directions, but diagnosis comes first.

---

## Core Mindset

Debug with the mindset of narrowing uncertainty step by step.

That means:

- symptoms are not causes
- first plausible explanation is not automatically the best one
- contradictions are useful
- reduction of search space is progress
- evidence beats intuition
- the goal is not just a fix, but a justified fix

A debug response should make the causal story clearer.

---

## Primary Priorities

In most debug tasks, prioritize roughly in this order:

1. define the symptom precisely
2. identify triggering conditions
3. narrow the search space
4. generate and rank hypotheses
5. isolate the most likely root cause
6. propose the smallest justified fix
7. define how to verify the fix
8. identify residual uncertainty

---

## Debug Responsibilities

### 1. Characterize the symptom
Clarify:
- what fails
- where it fails
- when it fails
- for whom it fails
- under what conditions it fails

### 2. Separate symptom from mechanism
Example:
- symptom: login occasionally times out
- possible mechanisms: DB saturation, external API stall, lock contention, retry storm

### 3. Manage multiple hypotheses
A good debugger does not commit too early.

### 4. Use evidence to eliminate
Look for observations that:
- support one explanation
- weaken another
- expose a hidden dependency
- narrow reproduction conditions

### 5. Identify root cause or best current candidate
If full certainty is unavailable, provide ranked explanations with confidence.

### 6. Define validation
A proposed fix is incomplete if it lacks a way to confirm the diagnosis.

---

## Debug Questions

Use these internally while debugging.

### Symptom questions
- What exactly is observed?
- What is the difference between expected and actual behavior?
- Is the failure deterministic, intermittent, or environment-specific?

### Trigger questions
- What inputs, timing, or environment conditions cause the issue?
- Did anything recently change?
- Is the issue load-related, sequence-related, or data-related?

### Hypothesis questions
- What are the most plausible causes?
- What evidence supports each?
- What evidence contradicts each?
- What observation would disprove the current leading hypothesis?

### Boundary questions
- Is the issue local or cross-system?
- Could framework/runtime behavior be involved?
- Does the failure occur before, during, or after an external dependency interaction?

### Fix questions
- What is the smallest change consistent with the diagnosis?
- What could go wrong if the diagnosis is incomplete?
- How will the fix be verified?

---

## Debug Output Style

A strong debug output usually includes:

- symptom summary
- key evidence
- ranked hypotheses
- most likely root cause
- fix direction
- validation plan
- open questions

Example pattern:

- Symptom: Playwright test intermittently times out waiting for modal visibility in CI
- Evidence: test uses fixed `waitForTimeout`, failure occurs only under CI load, locator is broad
- Leading hypothesis: modal render timing exceeds fixed delay under slower CI conditions
- Alternative hypothesis: locator matches hidden duplicate element
- Most likely root cause: timing-based synchronization combined with weak locator
- Fix direction: replace fixed delay with condition-based wait and tighten locator
- Validation: run repeated CI-focused retries and inspect trace output

---

## Hypothesis Discipline

Debug behavior should use explicit hypothesis control.

### Good practice
- keep top candidates visible
- rank by evidence
- revise as new facts arrive
- note what would falsify each hypothesis

### Poor practice
- "this feels like a transaction bug"
- "probably just flaky CI"
- anchoring on the first suspicious line
- treating workaround success as root-cause proof

---

## Root Cause Guidance

A root cause explanation should be more than "where the error happened."

A strong root cause usually includes:
- trigger
- underlying mechanism
- enabling condition
- why detection was delayed or difficult if relevant

Example:
Not enough:
- "The test failed because the selector timed out."

Better:
- "The test fails because it waits a fixed amount of time rather than the actual modal state, and CI slowness exposes that mismatch. The broad selector likely increases sensitivity by matching multiple states."

---

## Debug Under Incomplete Evidence

Often the full root cause cannot be confirmed immediately.

In that case:
- present ranked hypotheses
- say what is known
- say what would disambiguate
- avoid pretending closure

Example:
"Current evidence favors self-invocation bypassing Spring transaction proxying, but the call path is not shown. Confirm by checking whether this annotated method is invoked from the same bean instance."

---

## Debug What to Prefer

Prefer:
- precise symptom wording
- ranked hypotheses
- elimination-based reasoning
- targeted next checks
- smallest plausible correction
- verification tied to failure mechanism

Prefer statements like:
- "This stack trace suggests failure before repository execution."
- "The issue appears load-sensitive rather than input-sensitive."
- "This fix would address the leading hypothesis, but would not explain the alternate cache-collision theory."

---

## Debug What to Avoid

Avoid:
- collapsing all ambiguity too early
- proposing broad changes before diagnosis
- confusing correlation with cause
- relying on framework folklore
- declaring root cause from one weak signal
- skipping validation logic

Bad:
- "Add retries."

Better:
- "Retries may mask the symptom, but current evidence suggests the problem is transaction duration under remote dependency latency. Confirm that before adding retry behavior."

---

## Debug Anti-Patterns

### Anti-pattern 1: premature closure
Ending investigation at the first plausible explanation.

### Anti-pattern 2: symptom-only fixing
Treating surface failure without addressing the mechanism.

### Anti-pattern 3: no disconfirmation logic
Failing to ask what would prove the current theory wrong.

### Anti-pattern 4: environment blindness
Ignoring local vs CI vs staging vs production differences.

### Anti-pattern 5: workaround mislabeling
Presenting a mitigation as root-cause resolution.

### Anti-pattern 6: evidence drift
Using new speculation as if it were collected evidence.

---

## Debug Completion Criteria

A debug result is strong when it can answer:

1. what the symptom is
2. what conditions trigger it
3. what the leading hypotheses are
4. what evidence supports the leading explanation
5. what the likely root cause is
6. what fix is justified
7. how the fix should be validated
8. what remains uncertain

---

## Short Reminder

When debug is active:
- define the symptom precisely
- keep multiple hypotheses early
- separate cause from symptom
- use evidence to narrow
- propose only justified fixes
