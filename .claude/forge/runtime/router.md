# Runtime: Router

## Purpose

This file defines how a task is routed into a concrete module composition.

Routing determines:
- the primary behavior
- any justified secondary behaviors
- the active domains
- the workflow path
- the output template
- the quality checklists

The router is a runtime coordinator.
It is not a workflow stage and it is not a complete catalog of all local activation hints.

Detailed activation signals belong primarily in:
- `/behaviors/*`
- `/domains/*`

The router defines the routing algorithm and composition policy.

---

## Scope

This router applies only after `forge ask` resolves host ownership. Forge Runtime lifecycle intent, explicit `/skill` invocations, and native-first specialist classes are resolved before these Forge-internal composition rules. The authoritative boundary is `registry/skill-routing.json` `ask_policy`.

---

## Router Responsibilities

A routing decision should determine:

1. primary behavior
2. secondary behaviors if justified
3. active domains
4. workflow path
5. output template
6. quality checklists
7. routing confidence

The objective is minimum sufficient composition.
Do not activate more than the task needs.

---

## Routing Inputs

Useful routing inputs include:

- user request wording
- task verbs
- attached code, logs, or tests
- repository structure
- imports and annotations
- configuration files
- prior conversation context
- explicit output expectations

The router should use these to classify the task, not to replace deeper analysis.

---

## Routing Outputs

A routing result should be representable as:

- Primary behavior: `behavior.review`
- Secondary behaviors: `behavior.explain`
- Domains: `domain.java`, `domain.spring`, `domain.redis`
- Workflow path: `workflow.light_review`
- Template: `template.review_report`
- Checklists:
  - `checklist.general_quality`
  - `checklist.review`
  - `checklist.verification`
  - `checklist.delivery`

This structure may remain internal state.

---

## Mandatory Routed Task Types

The following task types must be routed before answer generation:
- review
- debug
- refactor
- optimize
- implementation planning
- test plan creation
- test report generation
- incident analysis
- structured document/artifact review

For these task types, the router is the default entry point, not an optional coordinator.
Free-form response generation must not bypass routing for any recognized task in this list.

---

## Skill Selection Policy

When a task matches a known mandatory routed type, check for a matching skill before assembling modules manually.

Skills are pre-composed, high-frequency task entry points defined in `.claude/skills/`. Each skill bundles a verified composition of behavior + domains + template + checklists + workflow.

### Skill matching priority

1. Check if the task matches any skill in `.claude/skills/` by trigger phrases and task shape
2. If a skill matches, prefer the skill's pre-verified composition over manual assembly
3. If no skill matches, fall through to manual routing via Behavior Selection Policy

### Available skills

| Skill | Primary Behavior | Workflow | Context |
|-------|-----------------|----------|---------|
| `skills/code-review` | review + review-routing | full_default / light_review | fork |
| `skills/debug` | debug | debug_analysis | fork |
| `skills/plan` | refactor or general | full_default | inherit |
| `skills/error-analysis` | debug (specialized) | debug_analysis | fork |
| `skills/report` | review or debug | full_default | inherit |
| `skills/explain` | explain | light_explanation | inherit |
| `skills/refactor` | refactor | full_default | fork |
| `skills/optimize` | optimize | full_default | fork |
| `skills/document` | document | full_default | inherit |
| `skills/test-design` | review | full_default | inherit |
| `skills/incident` | debug | debug_analysis | fork |
| `skills/test-implementation` | document | full_default | inherit |
| `skills/migration` | refactor | full_default | inherit |
| `skills/explore` | — | light_exploration | inherit |
| `skills/implement` | — | full_default | fork |
| `skills/architecture-design` | — | full_default | inherit |
| `skills/security-review` | review | full_default | fork |
| `skills/data-design` | — | full_default | inherit |
| `skills/dependency-audit` | review | light_review | fork |

### Skill variants

After choosing a primary skill, the router may select one opt-in variant when its
selector evidence is unambiguous. Variant fields replace only the parent fields
they declare; omitted fields inherit. This keeps a transition such as Vue 2 →
Vue 2.7 limited to its source/target domains instead of accumulating unrelated
or incompatible guidance. If no selector matches, the router keeps the base
skill composition and records no variant.


- Skills are **pre-verified** — the module composition is known to work for the task type
- Skills provide **consistent output quality** — every execution follows the same discipline
- Skills reduce **routing variance** — no risk of missing a domain or checklist
- Skills are the **fast path** for high-frequency general tasks, while packs remain the fast path for technology-specific tasks

If both a skill and a pack match, prefer the pack when the task is technology-specific (e.g., "Spring service review"), prefer the skill when the task is general (e.g., "review this code").

---

## Routing Algorithm

### Step 1: Identify the primary task mode
Determine what the user is fundamentally asking for.

Choose one primary behavior whenever possible.

Typical primary modes include:
- review
- debug
- refactor
- optimize
- document
- explain

### Step 2: Identify secondary task modes
Some tasks combine more than one mode.

Use secondary behaviors only when they materially improve the answer.

Examples:
- review + explain
- debug + review
- refactor + explain
- optimize + document

Secondary behaviors must not displace the primary one.

### Step 3: Activate relevant domains
Select only the technical domains that materially affect judgment.

Use:
- explicit technologies in the request
- repository and code signals
- known framework markers
- artifact type
- failure mode relevance

Detailed activation hints should come from each domain module.

### Step 4: Select the workflow path
Choose the smallest safe workflow path.

Use the full path by default for non-trivial engineering tasks.
Use lighter paths only when the task clearly allows it.

### Step 5: Select the output template
Choose the simplest template that matches the intended deliverable.

### Step 6: Select quality gates
Apply:
- general quality
- delivery
and add:
- behavior-specific checklist
- verification checklist when correctness matters

### Step 7: Record routing uncertainty
If routing is ambiguous, keep that uncertainty explicit.
Do not fake precision.

---

## Behavior Selection Policy

Behavior selection should be based on user intent, not just artifact type.

### Review
Use when the main need is evaluation, judgment, or issue-finding.

For detailed routing rules, see the review routing asset pack under `runtime/review-routing/`:
- `README.md` — pack overview and routing summary
- `review-routing-spec.md` — routing rules, context classification, output guard
- `review-routing-checklist.md` — pre-delivery validation checklist
- `review-routing-examples.md` — concrete routing examples and anti-examples
- `review-routing-workflow.md` — step-by-step execution workflow

### Debug
Use when the main need is diagnosis, causal explanation, or failure isolation.

### Refactor
Use when the main need is structural improvement with behavior preservation.

### Optimize
Use when the main need is efficiency or performance improvement.

### Document
Use when the main need is durable written communication for future readers.

### Explain
Use when the main need is understanding a concept, mechanism, or tradeoff.

For detailed activation signals, consult the behavior modules directly.

---

## Domain Selection Policy

Domain selection should be driven by technical relevance.

Activate a domain when:
- it changes how the task should be interpreted
- it adds material failure modes or constraints
- it affects review, diagnosis, refactor, optimization, or verification quality

Do not activate domains:
- merely because they exist somewhere in the repository
- merely because they are adjacent to the task
- merely "just in case"

For detailed activation signals, consult the domain modules directly.

---

## Workflow Path Selection Policy

The router should select from named workflow paths.

### `workflow.full_default`
Use for:
- non-trivial engineering tasks
- change-oriented work
- correctness-sensitive review/debug/refactor/optimize tasks

### `workflow.light_explanation`
Use for:
- conceptual explanation
- framework mechanism explanation
- compare-and-contrast explanation

### `workflow.light_review`
Use for:
- compact review tasks
- low-risk targeted code evaluation

### `workflow.debug_analysis`
Use for:
- diagnosis without direct code execution/change
- flaky test analysis
- root-cause investigation

### `workflow.blocked_task`
Use when:
- evidence is insufficient
- stronger progress requires more user input

The workflow registry should remain the canonical source for named paths.

---

## Template Selection Policy

Template choice should reflect deliverable shape.

Use:
- `template.review_report` for review-heavy outputs
- `template.debug_report` for diagnosis-heavy outputs
- `template.refactor_plan` for structural transformation plans
- `template.implementation_plan` for implementation or rollout planning
- `template.explanation` for teaching/explanation tasks
- `template.default` when no specialized structure is necessary

Prefer the simplest fitting template.

---

## Checklist Selection Policy

Always apply:
- `checklist.general_quality`
- `checklist.delivery`

Add:
- `checklist.review` when review is primary
- `checklist.debug` when debug is primary
- `checklist.refactor` when refactor is primary
- `checklist.verification` when correctness-sensitive claims are made

Checklist choice should reflect claim strength and task risk.

---

## Routing Constraints

The router should prefer:

- one primary behavior
- a small relevant domain set
- the smallest safe workflow path
- the lightest useful template
- quality gates proportional to risk

The router should avoid:

- behavior inflation
- domain inflation
- excessive keyword-driven routing
- over-formalization of tiny tasks
- under-structuring of risky tasks

---

## Routing Under Uncertainty

When routing is uncertain:

1. choose the most plausible primary mode
2. keep alternatives implicit or explicit as needed
3. reduce confidence where ambiguity matters
4. avoid recommendations that depend on unresolved routing assumptions
5. ask for clarification if routing ambiguity materially changes the answer

Uncertainty in routing is acceptable.
Hidden uncertainty is not.

---

## Routing Anti-Patterns

Avoid:

- turning the router into a full prompt encyclopedia
- duplicating detailed activation signals from all modules
- activating many domains for coverage rather than relevance
- treating every task as a full workflow
- treating every task as a minimal workflow
- allowing multiple primary behaviors

---

## Completion Criteria

Routing is complete when the runtime can clearly answer:

1. what the primary task mode is
2. which behavior is primary
3. which domains materially matter
4. which workflow path is appropriate
5. which template should shape delivery
6. which quality gates should be applied
7. how confident the routing decision is

If these are not clear, routing is incomplete.

---

## Short Reminder

The router is a coordinator.

It should:
- classify the task
- select the minimum sufficient modules
- choose the safest fitting workflow
- delegate detailed activation hints to behavior and domain modules
