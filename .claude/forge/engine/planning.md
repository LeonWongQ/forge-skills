# Engine: Planning

## Purpose

Planning converts conclusions into an intentional course of action.

This stage exists to prevent:
- impulsive changes
- unclear sequencing
- unbounded scope growth
- fixes without validation
- unnecessary risk
- execution that is disconnected from the task goal

Planning answers:
- what should be done
- in what order
- why this order is appropriate
- what risks must be controlled
- how success will be checked

Planning is required whenever meaningful action, change, or recommendation is involved.

---

## Core Objective

Define the smallest effective path from current state to desired outcome.

A strong Planning stage should answer:

- What outcome are we aiming for?
- What concrete steps are needed?
- What dependencies or prerequisites exist?
- What alternatives were considered?
- What risks come with each option?
- How will the result be verified?
- What should be deferred or left unchanged?

---

## Inputs

Planning uses:

- task definition from Discover
- evidence
- context
- reasoning outputs
- active behavior priorities
- domain constraints
- user constraints if explicit

Planning may occur:
- before a proposed change
- before an implementation outline
- before debugging next steps
- before rollout recommendations
- before a refactor sequence

---

## Outputs

Planning should produce some combination of:

- target outcome
- ordered action steps
- option comparison
- dependencies
- assumptions
- risk controls
- validation strategy
- rollback or mitigation notes
- explicit non-goals

These outputs may be internal or surfaced to the user depending on task type.

---

## Planning Responsibilities

### 1. Define the target state
State what success looks like.

Examples:
- bug no longer reproduces under the identified conditions
- service becomes easier to test without behavior change
- query avoids full table scan
- review findings are converted into a safe fix order
- documentation becomes accurate and usable for its audience

### 2. Convert conclusions into steps
Reasoning tells us what seems true.
Planning tells us what to do about it.

### 3. Sequence actions intentionally
The order of operations matters.

Good sequencing often:
- reduces risk early
- validates assumptions before larger changes
- isolates high-confidence improvements first
- preserves rollback options
- limits blast radius

### 4. Make validation part of the plan
A plan is incomplete if it says what to change but not how to confirm it worked.

### 5. Respect constraints
A theoretically ideal plan may still be wrong if it violates:
- compatibility constraints
- rollout constraints
- team conventions
- risk tolerance
- performance limits
- scope boundaries

---

## Planning Questions

Use these questions internally.

### Goal questions
- What is the exact desired outcome?
- Is the outcome corrective, preventive, structural, explanatory, or operational?

### Action questions
- What actions are required to reach the outcome?
- Which steps are necessary, optional, or premature?
- What can be done incrementally?

### Dependency questions
- What must be understood or changed first?
- Are there hidden dependencies on config, schema, tests, or runtime behavior?

### Risk questions
- What could break if this plan is wrong?
- What part of the plan carries the highest uncertainty?
- What minimizes blast radius?

### Validation questions
- How will we know the plan worked?
- What scenarios matter most to check?
- What remains risky even after implementation?

---

## Planning Process

### Step 1: State the objective
Write the goal in outcome terms, not action terms.

Better:
- prevent stale cache reads after update

Worse:
- add some Redis logic

### Step 2: Identify candidate approaches
There is often more than one possible path.
List viable options when tradeoffs matter.

### Step 3: Choose the preferred path
Select based on:
- correctness
- safety
- scope fit
- maintainability
- verification cost
- user need

### Step 4: Break into ordered steps
Sequence from least risky / most clarifying to more invasive work.

### Step 5: Attach validation to steps
Each meaningful step should have an associated check when possible.

### Step 6: Identify explicit non-goals
State what the plan will not attempt if scope discipline matters.

---

## Plan Granularity

The level of detail should match the task.

### Lightweight planning
Used for:
- small targeted reviews
- minor local fixes
- simple explanation-backed suggestions

Example:
1. confirm null handling path
2. add guard clause
3. run existing tests covering absent value behavior

### Medium planning
Used for:
- focused refactors
- bug fixes touching multiple functions
- test stabilization
- query tuning

Example:
1. isolate duplicated logic
2. extract helper with preserved contract
3. update call sites
4. run unit and integration tests
5. review edge-case parity

### Heavyweight planning
Used for:
- architectural refactors
- risky migrations
- distributed consistency fixes
- multi-step incident remediation

Example:
1. confirm current write/read consistency model
2. define safer invalidation strategy
3. introduce compatibility layer
4. deploy with metrics
5. monitor stale-read rate
6. remove legacy path after stabilization

---

## Planning by Behavior

### Review-oriented planning
If the task is review only, planning may mean:
- prioritize findings
- identify fix order
- separate must-fix from optional improvements
- suggest verification for each issue

### Debug-oriented planning
Planning often means:
- define next diagnostic steps
- order hypotheses by testability
- pick the fastest high-signal validation first
- avoid large fixes before root cause confirmation

### Refactor-oriented planning
Focus on:
- preserving behavior
- incremental transformation
- reducing coupling step by step
- maintaining test safety net

### Optimize-oriented planning
Focus on:
- confirm bottleneck
- choose highest-impact change first
- preserve correctness
- define measurable success criteria

### Document-oriented planning
Focus on:
- audience
- structure
- accuracy source
- examples
- gaps requiring clarification

### Explain-oriented planning
Focus on:
- teaching order
- mental model first
- details second
- examples and pitfalls

---

## Alternative Analysis

Planning should compare options when there is real choice.

Useful comparison dimensions:
- implementation complexity
- regression risk
- operational risk
- reversibility
- verification effort
- long-term maintainability
- short-term delivery speed

### Example
Option A:
- small local fix
- lower risk
- fast to ship
- does not remove structural duplication

Option B:
- broader refactor
- better long-term structure
- higher verification burden
- not justified if immediate production issue is urgent

---

## Risk-Control Planning

Every meaningful plan should consider risk control.

Possible controls:
- smaller step size
- feature flag
- compatibility layer
- extra assertions
- temporary logging
- staged rollout
- targeted tests
- rollback path

If the task is analysis-only, risk control may appear as recommendation rather than execution instruction.

---

## Assumptions in Planning

Planning may depend on assumptions.
Make them visible.

Examples:
- assuming all writes pass through this service
- assuming transaction boundaries are proxy-managed
- assuming Redis keys are globally shared
- assuming CI parallelism contributes to flakiness

An assumption-heavy plan should carry lower confidence.

---

## Non-Goals

Explicit non-goals help prevent sprawl.

Examples:
- does not redesign the caching strategy
- does not address unrelated style issues
- does not migrate all tests to a new fixture model
- does not change public API signatures

Non-goals are especially important for refactor and optimization tasks.

---

## Planning Anti-Patterns

### Anti-pattern 1: action without objective
Listing steps without stating what success means.

### Anti-pattern 2: sequencing by convenience
Doing steps in a pleasant order rather than a safe order.

### Anti-pattern 3: hidden assumptions
Relying on unstated conditions that may invalidate the plan.

### Anti-pattern 4: no validation strategy
Planning changes without planning how to confirm them.

### Anti-pattern 5: scope inflation
Turning a local fix into a broad redesign without need.

### Anti-pattern 6: false precision
Providing detailed plans for areas where evidence is still weak.

---

## Planning Completion Criteria

Planning is sufficient when the assistant can state:

1. the target outcome
2. the preferred approach
3. the ordered steps
4. key assumptions
5. major risks
6. how success will be verified
7. what is deliberately not included

If these are unclear, planning is incomplete.

---

## Short Reminder

Before moving to Execution, ensure:
- the goal is explicit
- the plan is sequenced
- risk is considered
- validation is built in
- scope is controlled
