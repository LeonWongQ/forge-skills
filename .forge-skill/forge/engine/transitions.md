# Engine: Transitions

## Purpose

This file defines how workflow stages connect to one another.

The core engine stages already define:
- purpose
- inputs
- outputs
- completion criteria

This file adds:
- entry conditions
- exit conditions
- skip conditions
- fallback conditions
- escalation conditions

Its goal is to make the workflow easier to operationalize in a runtime system.

---

## Why Transitions Matter

The engine is not just a linear list of stages.
A good runtime must also know:

- when a stage can start
- when a stage is complete enough to move on
- when a stage may be skipped
- when the flow must return to an earlier stage
- when confidence is too weak to proceed normally

Without transition rules, the workflow remains conceptually strong but operationally underspecified.

---

## Default Workflow

The default workflow remains:

```text
discover -> evidence -> context -> reasoning -> planning -> execution -> verification -> delivery
```

This file explains how transitions between those stages should work.

---

## Transition Rule Format

For each stage, define:

- **Entry Conditions**
- **Exit Conditions**
- **Skip Conditions**
- **Fallback Conditions**
- **Escalation Conditions**

Not every field is always used, but this is the standard model.

---

## Stage: Discover

### Entry Conditions
- a user request exists
- some task artifact, question, or signal exists

### Exit Conditions
- the task is framed sufficiently
- likely primary behavior is identified
- likely domains are identified
- immediate scope is understood
- important missing information is noted

### Skip Conditions
- **none**

Discover is mandatory.

### Fallback Conditions
- if user intent remains too ambiguous
- if artifact identity is unclear
- if multiple task interpretations materially change the answer

Fallback action:
- ask for clarification
- or proceed with explicitly bounded assumptions

### Escalation Conditions
- severe ambiguity affecting safety or correctness
- scope uncertainty that could invalidate the rest of the workflow

---

## Stage: Evidence

### Entry Conditions
- the task is framed enough to know what evidence is relevant

### Exit Conditions
- available artifacts are inventoried
- direct observations are captured
- important evidence sources are traceable
- assumptions are separated from facts
- major evidence gaps are visible

### Skip Conditions
May be skipped only when:
- the task is purely conceptual explanation
- no artifact-based claim is being made

### Fallback Conditions
- if evidence is too thin for meaningful reasoning
- if available evidence is contradictory and unresolved
- if critical artifacts are missing

Fallback action:
- request additional evidence
- or continue with lower confidence and explicit limits

### Escalation Conditions
- evidence conflict materially changes likely conclusion
- missing evidence blocks correctness-sensitive claims

---

## Stage: Context

### Entry Conditions
- enough evidence exists to situate the task in a system or concept context

### Exit Conditions
- relevant environment assumptions are identified
- dependencies or neighboring components are recognized
- meaningful constraints are visible
- runtime or framework conditions are considered

### Skip Conditions
May be skipped only when:
- the task is very small and local
- context adds little to safe interpretation
- the task is a compact, bounded review or explanation

### Fallback Conditions
- if context uncertainty weakens conclusions too much
- if system conditions are central but unknown
- if local evidence cannot be interpreted safely without environment understanding

Fallback action:
- return to evidence gathering
- or explicitly limit the claim scope

### Escalation Conditions
- hidden framework/runtime behavior is likely decisive
- deployment/config/runtime context may reverse the conclusion

---

## Stage: Reasoning

### Entry Conditions
- evidence and context are sufficient for at least bounded interpretation

### Exit Conditions
- findings, hypotheses, or conclusions are formed
- important claims are linked to evidence
- uncertainty is calibrated
- alternatives are considered where needed
- impact is explained

### Skip Conditions
- **none** for meaningful technical tasks

Even explanation-oriented tasks still require reasoning.

### Fallback Conditions
- if evidence is too weak to support meaningful conclusion
- if contradictions remain unresolved
- if likely interpretations are too unstable

Fallback action:
- return to evidence
- return to context
- or switch to blocked delivery with explicit unknowns

### Escalation Conditions
- high-impact claim with weak support
- unresolved contradiction near a correctness-critical conclusion

---

## Stage: Planning

### Entry Conditions
- there is a meaningful conclusion or target outcome
- action or recommendation is needed

### Exit Conditions
- target outcome is explicit
- preferred approach is selected
- action sequence is defined
- major risks are identified
- validation path is included

### Skip Conditions
May be skipped when:
- the task is explanation-only
- the task is a very small review with no execution recommendation
- the final answer does not require a change plan

### Fallback Conditions
- if the preferred action depends on unresolved diagnosis
- if risks are too unclear
- if there is no justified approach yet

Fallback action:
- return to reasoning
- gather more context
- reduce claim strength

### Escalation Conditions
- broad or risky change surface
- high uncertainty in chosen path
- strong need for rollback or staged rollout planning

---

## Stage: Execution

### Entry Conditions
- a plan or action path exists
- scope and objective are clear enough to act

### Exit Conditions
- planned actions are performed or proposed
- deviations are recorded
- changes remain scoped
- result is ready for verification

### Skip Conditions
May be skipped when:
- the task is analysis-only
- the user asked for diagnosis or review without code changes
- explanation is the only deliverable

### Fallback Conditions
- if new evidence invalidates the plan
- if hidden dependencies emerge
- if action reveals broader scope than expected

Fallback action:
- return to planning
- return to reasoning
- split task into immediate and deferred parts

### Escalation Conditions
- accidental scope growth
- hidden contract change risk
- execution reveals major adjacent issue

---

## Stage: Verification

### Entry Conditions
- there is a meaningful claim, recommendation, or change to validate

### Exit Conditions
- verified and unverified areas are clearly separated
- success criteria are addressed
- residual risks are visible
- confidence is calibrated

### Skip Conditions
May be skipped only when:
- the task is purely conceptual
- no correctness or success claim is being made

Verification should **not** be skipped for:
- bug-fix claims
- correctness claims
- performance claims
- behavior-preservation claims

### Fallback Conditions
- if validation fails
- if verification reveals regression risk
- if success criteria are not actually met

Fallback action:
- return to execution
- return to planning
- return to reasoning if the causal model was wrong

### Escalation Conditions
- high-impact change with weak validation
- partial verification being mistaken for full confirmation

---

## Stage: Delivery

### Entry Conditions
- there is enough material to provide a useful answer
- selected template and checklist context are available

### Exit Conditions
- output is usable
- result or current best conclusion is clear
- uncertainty is visible where needed
- next step is actionable
- structure matches task needs

### Skip Conditions
- **none**

Delivery is mandatory.

### Fallback Conditions
- if the answer is technically correct but not usable
- if key uncertainty is hidden
- if the result does not match user need

Fallback action:
- return to verification
- return to reasoning
- simplify or restructure the output

### Escalation Conditions
- high-risk conclusion buried in dense text
- user cannot act from the current response
- structure mismatch obscures key outcome

---

## Cross-Stage Fallback Patterns

Common fallback loops include:

### Reasoning -> Evidence
Use when:
- conclusion support is weak
- contradictions remain unresolved

### Reasoning -> Context
Use when:
- local observations cannot be interpreted safely without system conditions

### Planning -> Reasoning
Use when:
- action path depends on unconfirmed diagnosis or unstable assumptions

### Execution -> Planning
Use when:
- implementation reveals new constraints or invalidates original sequencing

### Verification -> Execution
Use when:
- change did not actually solve the target issue
- regression risk appears

### Verification -> Reasoning
Use when:
- the causal model or interpretation appears wrong

### Delivery -> Verification
Use when:
- the answer overstates what was actually confirmed

---

## Transition Philosophy

Transitions should optimize for:

- enough rigor to avoid false confidence
- enough flexibility to support real task variation
- explicit fallback rather than silent drift
- proportionality to task risk

This file should not force every task into the heaviest path.
It should prevent hidden stage skipping and unsupported certainty.

---

## Short Reminder

Stages are not just ordered.
They are gated.

A good runtime should know:
- when to move forward
- when to loop back
- when to stop and ask
- when to downgrade confidence
