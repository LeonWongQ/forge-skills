# Engine: Discover

## Purpose

Discover is the entry stage of task execution.
Its purpose is to determine what problem is actually being worked on before deeper analysis begins.

This stage prevents:
- solving the wrong problem
- using the wrong behavior
- applying irrelevant domains
- drifting into accidental scope expansion
- making conclusions before the task is understood

Discover is required for almost every task, even when it is brief.

---

## Core Objective

Turn an initial request, artifact, or signal into a clear working task definition.

A strong Discover stage should answer:

- What is the user asking for?
- What artifact or system is involved?
- What type of task is this?
- What is in scope?
- What is out of scope?
- What information is missing?
- What kind of result will the user likely need?

---

## Inputs

Potential inputs include:

- user message
- repository or file context
- code snippets
- stack traces
- logs
- screenshots
- diffs
- test failures
- config files
- prior conversation context

Inputs may be:
- complete
- partial
- noisy
- ambiguous
- contradictory

Discover exists partly to normalize that ambiguity.

---

## Outputs

The Discover stage should produce a concise internal task definition containing:

- task statement
- primary behavior candidate
- secondary behavior candidates if any
- likely domain candidates
- scope definition
- constraints
- expected deliverable type
- missing information list
- initial risk notes
- confidence in task understanding

These do not always need to be shown to the user, but they should guide all downstream work.

---

## Discover Responsibilities

### 1. Identify user intent
Determine what outcome the user actually wants.

Examples:
- find issues
- explain behavior
- fix a bug
- improve structure
- optimize performance
- generate documentation
- compare approaches

User wording may be imprecise.
Interpret intent carefully, not literally.

### 2. Identify the working artifact
Determine what the request is about:
- a method
- a class
- a module
- a query
- a test
- a service interaction
- an architectural pattern
- a runtime incident

### 3. Classify task type
Map the task to one or more behavior modes.

Typical mappings:
- "review this code" -> review
- "why does this fail?" -> debug
- "clean this up" -> refactor
- "make this faster" -> optimize
- "write docs" -> document
- "explain this" -> explain

### 4. Establish scope boundaries
Clarify:
- what the user directly asked about
- what adjacent areas may matter
- what should not be analyzed unless needed

### 5. Detect missing prerequisites
Identify what cannot be known yet.
Examples:
- no failing logs
- no code path shown
- no environment details
- no expected behavior defined
- missing schema or test context

### 6. Anticipate useful output shape
Infer whether the user likely needs:
- findings
- root cause analysis
- step-by-step plan
- patch proposal
- conceptual explanation
- structured report

---

## Discover Questions

Use these questions internally.

### Intent questions
- What does success look like from the user's perspective?
- Is the user asking for diagnosis, judgment, transformation, explanation, or implementation?
- Is the request tactical or strategic?

### Artifact questions
- What exact artifact is under discussion?
- Is the artifact complete or partial?
- Is the artifact representative of the issue, or only a symptom fragment?

### Scope questions
- Is the request local or system-wide?
- Are there obvious boundary conditions?
- Are there adjacent concerns that are critical to mention?

### Constraint questions
- Are there constraints on changing behavior?
- Are compatibility, rollout, performance, or safety concerns implied?
- Is this production-sensitive?

### Missing-info questions
- What key piece of information would most reduce uncertainty?
- Is progress blocked without that information?
- Can meaningful partial analysis still be done?

---

## Discover Process

### Step 1: Parse the request at face value
Extract the direct ask without overinterpreting it.

Example:
"Can you review this Redis caching code?"
Direct ask:
- perform a review
- focus on Redis caching code

### Step 2: Infer likely deeper intent
Determine whether the user may care about something beyond the literal wording.

Example:
"Can you review this Redis caching code?"
Likely deeper concerns may include:
- consistency
- stampede risk
- TTL correctness
- concurrency
- invalidation safety

Do not assume these are definitely required, but keep them available.

### Step 3: Identify task mode
Choose primary behavior and possible secondary behaviors.

Example:
- primary: review
- secondary: explain if the user also needs rationale

### Step 4: Identify relevant artifact scope
Determine whether the analysis target is:
- the provided snippet only
- the surrounding module
- the runtime behavior implied by the snippet
- a broader design pattern

### Step 5: Identify unknowns and blockers
List missing details.
Examples:
- no repository context
- no schema
- no logs
- no expected output
- missing surrounding method calls

### Step 6: Decide whether to proceed or ask
If enough information exists for useful work, proceed.
If not, deliver a scoped request for missing data.

---

## Discover Heuristics by Task Type

### Review-oriented discovery
Focus on:
- what code/change is being evaluated
- what quality dimensions matter
- whether the user wants broad or targeted review

Useful clarifications:
- full review or focus area?
- code snippet or full file?
- correctness only or also maintainability/performance?

### Debug-oriented discovery
Focus on:
- exact symptom
- reproduction conditions
- expected vs actual behavior
- timing and environment
- recent changes if known

Useful clarifications:
- what fails?
- where?
- when?
- under what inputs or environment?

### Refactor-oriented discovery
Focus on:
- what pain point motivates refactoring
- whether behavior must stay identical
- whether scope is local or architectural

Useful clarifications:
- reduce duplication?
- improve testability?
- split responsibilities?
- preserve public API?

### Optimize-oriented discovery
Focus on:
- what metric matters
- what the bottleneck likely is
- whether evidence exists

Useful clarifications:
- latency, memory, throughput, cost?
- current baseline?
- user-perceived or infrastructure-perceived issue?

### Explain-oriented discovery
Focus on:
- target audience
- depth level
- conceptual vs implementation explanation

Useful clarifications:
- beginner or experienced engineer?
- broad overview or detailed mechanism?
- compare alternatives or explain one path?

---

## Scope Definition Rules

A good scope statement should identify:

- primary analysis target
- allowed adjacent analysis
- excluded or deferred concerns

### Example
Request:
"Review this Spring service for transaction issues."

Possible scope:
- in scope: transaction boundaries, propagation assumptions, exception handling, persistence interaction
- near scope: service layering if it directly affects transaction correctness
- out of scope by default: unrelated naming/style issues unless severe

---

## Ambiguity Handling

Ambiguity is common at discovery time.

### If user intent is ambiguous
Choose the most likely interpretation, but keep alternatives alive.

Example:
"Look at this change"
Possible meanings:
- review
- explain
- debug regression

Use a cautious review-oriented discovery unless context strongly indicates otherwise.

### If multiple tasks are embedded
Separate them internally.

Example:
"Review this fix and tell me whether it will solve the production issue."
Split into:
- review the fix
- assess whether the fix addresses the root cause

### If the request is under-specified
Proceed with bounded analysis if possible.
Do not block prematurely if useful partial work can still be done.

---

## Discover Deliverable Contract

At the end of Discover, the assistant should internally be able to state something like:

- Task: review a Spring Boot service for transactional correctness and failure risks
- Primary behavior: review
- Secondary behavior: explain
- Domains: java, spring, testing
- Scope: provided service logic and directly related transaction semantics
- Missing info: repository-wide transaction config, repository method behavior
- Planned output: review findings with severity and suggested fixes
- Confidence in task framing: medium

This level of clarity is usually sufficient to start evidence collection.

---

## Discover Failure Modes

Avoid these mistakes.

### Failure mode 1: premature solutioning
Jumping to fixes before understanding the task.

### Failure mode 2: literal-only interpretation
Missing the real user need because the wording was shallow.

### Failure mode 3: silent scope expansion
Reviewing unrelated parts of the system without disclosure.

### Failure mode 4: over-blocking
Demanding perfect information before doing any useful work.

### Failure mode 5: under-asking
Proceeding with false certainty when one targeted clarification would prevent major error.

---

## Discover Completion Criteria

Discover is complete when the assistant can answer:

1. What is the task?
2. What type of work is this?
3. What artifact is involved?
4. What is the immediate scope?
5. What information is missing?
6. What kind of output is most useful next?

If these cannot be answered, Discover is incomplete.

---

## Short Reminder

Before moving to Evidence, ensure:
- the task is framed
- the likely behavior is selected
- scope is explicit
- key unknowns are identified
- enough clarity exists to analyze meaningfully
