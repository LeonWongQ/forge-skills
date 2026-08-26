# Engine: Reasoning

## Purpose

Reasoning transforms evidence and context into justified conclusions.

This stage does not merely summarize observations.
It explains:
- what they mean
- why they matter
- what is likely happening
- how strongly the conclusion is supported
- what alternatives remain possible

Reasoning is where judgment happens, but it must remain disciplined.

Reasoning prevents:
- unsupported conclusions
- mixing symptoms with causes
- overclaiming certainty
- shallow recommendations
- evidence being collected without being interpreted

---

## Core Objective

Produce conclusions, hypotheses, and tradeoff judgments that are explicitly grounded in evidence and context.

A strong Reasoning stage should answer:

- What conclusions are justified?
- What is most likely versus merely possible?
- What impact follows from the observations?
- What remains uncertain?
- What should happen next based on current confidence?

---

## Inputs

Reasoning uses:

- evidence from `/engine/evidence.md`
- context from `/engine/context.md`
- active behavior priorities
- active domain knowledge
- task scope from Discover

Reasoning should not invent facts that were not observed or clearly labeled as assumptions.

---

## Outputs

Reasoning should produce some combination of:

- findings
- ranked hypotheses
- root-cause candidates
- impact analysis
- tradeoff analysis
- confidence levels
- unresolved questions
- next validation steps

---

## Reasoning Responsibilities

### 1. Interpret observations
Explain the significance of evidence.

Example:
Observation:
- a transaction wraps a call to an external API

Reasoning:
- this may extend transaction duration and increase lock holding time
- this raises risk under latency or retry conditions

### 2. Distinguish symptoms from causes
Especially important in debugging.

Example:
Symptom:
- timeout in CI
Possible causes:
- unstable locator
- timing-based wait
- resource contention
- environment slowness

Do not collapse these into one too early.

### 3. Rank likelihood
When certainty is not available, rank plausible explanations.

### 4. Connect findings to impact
Explain why the finding matters:
- correctness
- reliability
- performance
- maintainability
- testability
- operational safety

### 5. Bound conclusions by confidence
Reasoning should be calibrated, not theatrical.

---

## Reasoning Structure

A useful micro-structure for important conclusions:

1. Observation
2. Interpretation
3. Why it matters
4. Confidence
5. What would verify it further

### Example
- Observation: the cache key does not include tenant ID
- Interpretation: values from different tenants may collide in shared cache space
- Why it matters: this risks cross-tenant data leakage or incorrect reads
- Confidence: high if cache is globally shared
- Further verification: confirm cache namespace and tenant isolation strategy

---

## Types of Reasoning Outputs

### Findings
Used mostly in review tasks.

Structure:
- issue
- evidence
- impact
- severity
- suggested direction

### Hypotheses
Used mostly in debug tasks.

Structure:
- candidate explanation
- supporting evidence
- contradictory evidence
- likelihood
- validating observation

### Tradeoff analysis
Used mostly in refactor, optimize, and design tasks.

Structure:
- option
- benefits
- costs
- risk
- fit for current constraints

### Root-cause assessment
Used when the goal is diagnosis.

Structure:
- symptom
- suspected mechanism
- supporting evidence
- competing explanations
- confidence
- next validation step

---

## Reasoning Modes by Behavior

### Review reasoning
Focus on:
- correctness risks
- edge cases
- maintainability concerns
- testability gaps
- hidden coupling
- contract mismatches

### Debug reasoning
Focus on:
- narrowing hypotheses
- identifying causal chain
- separating trigger from root cause
- using contradictions to refine likelihood

### Refactor reasoning
Focus on:
- complexity sources
- responsibility boundaries
- unnecessary coupling
- behavior preservation risk
- transformation sequencing

### Optimize reasoning
Focus on:
- bottleneck plausibility
- expected gain
- tradeoff cost
- measurement confidence
- scalability implications

### Explain reasoning
Focus on:
- conceptual correctness
- causal clarity
- mechanism ordering
- mental model accuracy

---

## Hypothesis Handling

When debugging or investigating uncertain behavior, use disciplined hypothesis management.

### Good hypothesis practice
- keep multiple candidates alive initially
- rank by evidence, not intuition
- explicitly note disconfirming evidence
- update confidence as new evidence appears

### Poor hypothesis practice
- anchoring on the first plausible explanation
- ignoring contradictory signals
- treating possibility as probability
- calling something root cause before validation

---

## Causality Rules

Reasoning should ask:

- What happened?
- What triggered it?
- What allowed it?
- What amplified it?
- What prevented detection earlier?

This is especially useful in incident analysis.

### Example distinction
- trigger: external API latency spike
- enabling condition: long transaction includes remote call
- amplification: retries under lock contention
- detection gap: no alert on transaction duration

This produces stronger reasoning than "the API was slow."

---

## Confidence Calibration

Confidence should depend on:
- quality of evidence
- completeness of context
- presence of contradictory signals
- specificity of observed mechanism

### High confidence
Use when:
- evidence is direct
- mechanism is clear
- alternatives are weak
- context is sufficiently known

### Medium confidence
Use when:
- evidence is meaningful but incomplete
- mechanism is plausible
- alternative explanations remain possible

### Low confidence
Use when:
- evidence is sparse
- context is weak
- inference depends heavily on assumptions

Do not inflate confidence to sound decisive.

---

## Tradeoff Reasoning

When more than one valid approach exists, reasoning should compare them.

Useful dimensions:
- correctness
- risk
- simplicity
- maintainability
- performance
- operational complexity
- rollout safety
- backward compatibility

Example:
"A narrower fix reduces immediate risk, but leaves duplication intact.
A broader refactor improves structure, but raises change surface and verification burden."

That is better than presenting one option as obviously best without context.

---

## Contradiction-Aware Reasoning

Contradictions should shape reasoning.

Example:
- user reports intermittent failure
- test fails deterministically
Possible reasoning:
- there may be two issues
- local test harness may not match production path
- the deterministic failure may expose a precondition for the intermittent one

Contradictions are often clues, not noise.

---

## Severity and Impact Reasoning

For review tasks, reasoning should distinguish:
- issue existence
- impact magnitude
- likelihood
- severity

An issue may be:
- real but low impact
- rare but severe
- common but recoverable
- maintainability-heavy rather than correctness-heavy

Do not assign severity based only on technical elegance.

---

## Reasoning Anti-Patterns

### Anti-pattern 1: conclusion without bridge
Jumping from evidence to claim without explaining the connection.

### Anti-pattern 2: symptom-cause collapse
Treating observed failure as the underlying cause.

### Anti-pattern 3: certainty theater
Using confident language to mask weak evidence.

### Anti-pattern 4: single-hypothesis fixation
Not considering alternatives early enough.

### Anti-pattern 5: impact omission
Identifying an issue without explaining why it matters.

### Anti-pattern 6: generic reasoning
Using abstract best-practice rhetoric instead of local analysis.

---

## Reasoning Completion Criteria

Reasoning is sufficient when the assistant can state:

1. what conclusions are justified now
2. what evidence supports them
3. what alternative interpretations remain
4. what impact follows
5. how confident the conclusion is
6. what should be validated or done next

If these are not clear, reasoning is incomplete.

---

## Short Reminder

Before moving to Planning, Execution, Verification, or Delivery, ensure:
- conclusions are evidence-linked
- impact is explained
- uncertainty is visible
- alternatives were considered where needed
- confidence is calibrated
