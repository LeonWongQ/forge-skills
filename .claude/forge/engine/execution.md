# Engine: Execution

## Purpose

Execution carries out the plan in a controlled, scoped, and traceable way.

This stage is where recommendations become concrete:
- edits
- proposals
- code transformations
- diagnostic actions
- structured outputs
- procedural steps

Execution exists to prevent:
- plan drift
- unrelated changes
- hidden assumption changes
- accidental behavior change
- opaque modifications
- over-editing

Execution should be disciplined, narrow, and reversible when possible.

---

## Core Objective

Apply the planned actions faithfully while preserving scope, intent, and traceability.

A strong Execution stage should answer:

- What exactly was done?
- What changed?
- Did anything deviate from plan?
- Was scope preserved?
- What intermediate results emerged?
- What still requires verification?

---

## Inputs

Execution uses:

- approved or selected plan
- active behavior guidance
- active domain constraints
- relevant artifacts and files
- stated assumptions
- validation intentions

Execution may involve:
- code changes
- config changes
- test changes
- textual documentation updates
- reasoning-backed fix proposals
- structured diagnostic procedures

---

## Outputs

Execution should produce:

- completed actions
- modified artifacts or proposed diffs
- execution notes
- deviations from plan if any
- newly discovered issues
- verification handoff inputs

These outputs should make it easy to review what happened.

---

## Execution Responsibilities

### 1. Follow the plan
Execution should implement the chosen path, not improvise a new task.

### 2. Keep changes scoped
Only touch what is necessary for the current objective unless a broader edit is explicitly justified.

### 3. Preserve intent
If the task is refactor, preserve external behavior.
If the task is bug fix, avoid accidental redesign unless required.
If the task is review-only, execution may be limited to recommendations instead of edits.

### 4. Record deviations
If reality forces a plan change, record:
- what changed
- why
- what new risk it introduces

### 5. Prepare verification
Execution is not complete when edits are made.
It is complete when the result is ready to be verified.

---

## Execution Modes

### Proposal-only execution
Used when the assistant should recommend changes rather than apply them directly.

Outputs:
- suggested edits
- patch outline
- example replacement code
- procedural steps

### Direct modification execution
Used when the assistant is expected to produce or simulate actual changed content.

Outputs:
- revised code
- edited config
- updated tests
- rewritten documentation

### Investigative execution
Used in debug tasks where execution may mean:
- running diagnostic reasoning steps
- defining targeted observations to gather
- narrowing hypotheses through procedural checks

Execution is broader than file editing, but must still be traceable.

---

## Execution Process

### Step 1: Re-anchor on objective
Before editing or proposing changes, confirm:
- what outcome is being pursued
- what constraints must be preserved

### Step 2: Apply the smallest justified change
Prefer minimal sufficient transformation first.

### Step 3: Keep edits coherent
Avoid mixing:
- bug fix + style cleanup
- refactor + unrelated renaming
- optimization + speculative architecture changes

unless explicitly justified.

### Step 4: Watch for newly exposed issues
Execution may reveal hidden dependencies or assumptions.
Do not silently absorb them into scope.

### Step 5: Record what was done
Make it possible to answer:
- which files or components changed
- what logic changed
- what did not change
- where uncertainty remains

---

## Execution Discipline

### Narrowness
A good execution step changes only what is needed.

### Coherence
A set of related edits should support one clear purpose.

### Local reasoning
Every edit should have a reason tied to:
- a finding
- a hypothesis
- a plan step
- a constraint

### Preservation
Respect existing contracts unless changing them is the actual goal.

### Visibility
Do not make consequential changes implicitly.

---

## Behavior-Specific Execution

### Review behavior
Execution may mean:
- produce findings
- annotate issues
- suggest fixes
- prioritize remediation

Review does not always imply changing code.

### Debug behavior
Execution may mean:
- define diagnostic checks
- narrow root-cause candidates
- propose minimal corrective edits
- identify confirmation steps

### Refactor behavior
Execution should emphasize:
- small structural moves
- stable external behavior
- responsibility separation
- readability improvement
- test safety

### Optimize behavior
Execution should emphasize:
- bottleneck-targeted changes
- measurable intended gain
- correctness preservation
- bounded complexity increase

### Document behavior
Execution should emphasize:
- accuracy
- readability
- audience fit
- structure
- examples

### Explain behavior
Execution should emphasize:
- conceptual ordering
- clarity
- examples
- caveats
- usefulness

---

## Handling Deviations

Sometimes execution cannot follow the original plan exactly.

### Valid reasons for deviation
- hidden dependency discovered
- assumption disproven
- smaller safer path found
- implementation obstacle encountered
- verification concerns emerged mid-change

### Deviation handling rule
If a deviation occurs, record:
- original step
- actual step taken
- reason
- impact on risk or verification

Unrecorded deviation weakens trust.

---

## Scope Control During Execution

Execution is where scope creep most often happens.

### Stay in scope by default
Do not clean up nearby code merely because it looks messy.

### Expand only when justified
Allowed reasons:
- directly required for correctness
- needed for compilation/integration
- needed for safe verification
- addresses a severe adjacent risk discovered during work

### Label expansions
If additional issues are touched, state:
- why they were necessary
- whether they are part of the main objective

---

## Execution Anti-Patterns

### Anti-pattern 1: opportunistic cleanup
Using a task as an excuse to make unrelated edits.

### Anti-pattern 2: untracked plan drift
Changing direction without acknowledging it.

### Anti-pattern 3: hidden contract change
Altering external behavior under the label of refactor.

### Anti-pattern 4: over-editing
Making a broader change than evidence and plan justified.

### Anti-pattern 5: unverifiable execution
Changing things in a way that cannot be meaningfully checked.

### Anti-pattern 6: justification loss
Producing edits without clear linkage to findings or plan steps.

---

## Execution Completion Criteria

Execution is sufficient when the assistant can state:

1. what was changed or proposed
2. why each meaningful change was made
3. whether the plan was followed
4. whether any deviations occurred
5. what still needs verification
6. whether any new issues were discovered

If these are unclear, execution is incomplete.

---

## Short Reminder

Before moving to Verification, ensure:
- the change is scoped
- the rationale is preserved
- deviations are recorded
- no unrelated edits were introduced
- the result is ready to be checked
