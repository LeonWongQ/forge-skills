# Runtime: Contract

## Purpose

This file defines the runtime execution contract for the modular assistant system.

It explains:
- how modules are assembled at runtime
- what internal state should exist
- what invariants must hold while executing a task
- what simplifications are allowed
- what cannot be skipped safely

This file does not replace the engine stages.
It governs how the runtime should use them.

---

## Runtime Model

A task should be handled through layered composition:

1. load global principles
2. route the task
3. construct runtime state
4. execute the selected workflow path
5. apply quality gates
6. deliver the result
7. optionally emit a persistent report artifact

---

## Runtime State

A runtime execution should maintain internal state equivalent to:

- task statement
- user goal
- primary behavior
- secondary behaviors
- active domains
- selected engine path
- selected template
- selected checklists
- scope
- constraints
- assumptions
- evidence items
- findings or hypotheses
- plan if applicable
- verification status
- open questions
- final confidence posture

This state does not need to be displayed in full, but it should remain coherent.

---

## Runtime Invariants

The following invariants should hold across almost all tasks.

### Invariant 1: task clarity before deep work
The runtime should know:
- what the user wants
- what artifact is involved
- what task mode is primary
- what information is missing

### Invariant 2: facts separated from assumptions
At all times, runtime state should distinguish:
- observed evidence
- inferred interpretation
- assumption
- unresolved question

### Invariant 3: scope remains explicit
The runtime should not silently drift into broader tasks unless:
- it is required for correctness
- it is required for safety
- the scope expansion is explicitly labeled

### Invariant 4: important claims remain traceable
The runtime should be able to tie important conclusions back to evidence and reasoning.

### Invariant 5: final output is usable
Even partial or blocked tasks should still deliver:
- current findings
- missing information
- best safe next step

---

## Runtime Sequence

### Phase 1: load kernel
Load:
- `CLAUDE.md`

This defines the global operating posture.

### Phase 2: route the task
Load and apply:
- `runtime/router.md`

This determines the module composition.

### Phase 3: instantiate execution path
Select:
- engine stages
- behavior
- domains
- template
- checklists

### Phase 4: execute workflow
Run the chosen engine path in order.

### Phase 5: run quality gates
Before final output, apply:
- general quality
- behavior-specific checklist if active
- verification checklist when relevant
- delivery checklist

### Phase 6: deliver
Produce final output shaped by the selected template.

### Phase 7: optionally persist artifact
If needed, emit:
- task report
- incident report
- review summary

---

## Allowed Simplifications

The runtime may simplify only when quality is preserved.

### Safe simplifications
- skip execution for explanation-only tasks
- use a light review path for small focused review tasks
- use the default template for small direct answers
- stop at blocked delivery when evidence is insufficient

### Conditional simplifications
- reduce planning depth for very small local fixes
- reduce context depth when the task is purely conceptual
- keep verification lighter for non-correctness explanatory tasks

### Unsafe simplifications
- skipping discover on ambiguous tasks
- skipping evidence in diagnosis or review-heavy tasks
- skipping verification while claiming correctness
- skipping delivery structure on substantial tasks
- silently ignoring major uncertainty

---

## Required Runtime Safeguards

### Safeguard 1: discovery is mandatory
Every task must pass through some form of task framing.

### Safeguard 2: delivery is mandatory
Every task must end in a usable response, even if incomplete.

### Safeguard 3: verification is mandatory for strong correctness claims
If the runtime claims:
- bug fixed
- issue confirmed
- refactor preserves behavior
- optimization improves performance
then verification must either exist or the claim must be downgraded appropriately.

### Safeguard 4: uncertainty must not be hidden
Missing evidence, partial validation, and ambiguous routing must remain visible in internal reasoning and final delivery when relevant.

---

## Runtime Modes

### Conversational mode
Use when:
- the task is small
- the output is direct
- persistent artifact is unnecessary

### Structured response mode
Use when:
- the task is non-trivial
- template-guided output improves clarity

### Artifact mode
Use when:
- output should be stored, handed off, or reused
- incident/review/task record is needed

---

## Runtime Error Handling

If the runtime becomes blocked:

1. stop escalation of unsupported certainty
2. summarize what is known
3. identify the highest-value missing information
4. identify what remains unverified
5. provide the best safe next step
6. deliver partial value rather than failing silently

---

## Runtime Drift Controls

The runtime should prevent:

- uncontrolled domain growth within one task
- multiple primary behaviors
- accidental shift from diagnosis into redesign
- accidental shift from review into implementation
- template inflation for small tasks
- claim inflation beyond verification level

---

## Runtime Completion Criteria

A runtime execution is strong when:

1. the right modules were chosen
2. the workflow path was appropriate
3. evidence and reasoning remained traceable
4. scope stayed controlled
5. verification matched the strength of the claims
6. the final output is actionable and honest

---

## Short Reminder

Runtime contract means:
- compose intentionally
- maintain coherent internal state
- simplify carefully
- verify important claims
- always deliver usable output
