# Integration: OpenAI Agents

## Purpose

This document explains how to use this repository in an OpenAI-style agent or agent-runtime system.

This includes environments where you may have:
- a system prompt layer
- developer instructions
- tool usage
- routing logic
- stateful task execution
- structured output expectations
- optional multi-step orchestration

This repository is especially useful in OpenAI-style systems because it already separates:
- principles
- workflow
- behavior
- domain expertise
- output structure
- quality gates

That separation maps well to agent architectures.

---

## Core Mapping

A practical mapping to an OpenAI-style agent system is:

- system-level core rules -> `CLAUDE.md`
- routing / planning logic -> `/runtime/router.md`, `/runtime/runtime-contract.md`
- behavior activation -> `/behaviors/*`
- domain activation -> `/domains/*`
- response schema guidance -> `/templates/*`
- quality gate / self-check layer -> `/checklists/*`
- persistent artifact shape -> `/reports/*`

This allows you to build either:
- one dynamic generalist agent
- or multiple specialized agents sharing the same repository

---

## Forge Thin Runtime Handoff

Forge can provide a provider-neutral handoff document before an API agent is called:

```text
route / compose → resolve manifest → runtime-init → runtime-prepare
external host call → normalized result → runtime-import-result → validate-runtime-output
```

The `runtime-prepare` payload carries the selected module paths, runtime state, requested engine stage, selected output template/schema, constraints, and a correlation digest. An external integration translates that payload into its own model request and returns a normalized JSON result with `runtime_id`, `adapter_id`, `status`, optional structured output/evidence, diagnostics, and opaque provider metadata.

Forge also provides a separate `context-bundle` handoff for hosts that require full materialized instructions. The bundle captures selected Markdown modules in deterministic layer order as strict UTF-8 text with byte counts and SHA-256 digests. Hosts should inject the captured content into their own system/developer prompt layout rather than rereading serialized paths. The Runtime Envelope remains the dynamic task/state/ledger record; Context Bundle generation itself never invokes a provider.


---


### Model 1: Single dynamic agent
One agent dynamically selects:
- behavior
- domains
- template
- checklists

Best when:
- you want one general engineering assistant
- routing can happen at runtime
- context loading is selective

### Model 2: Multi-agent specialization
Different agent types may preload different packs.

Examples:
- Review agent -> review + common code domains
- Debug agent -> debug + evidence/context-heavy engine set
- Refactor agent -> refactor + planning/execution/verification emphasis
- Explain agent -> explain + explanation template

Best when:
- task types are frequently distinct
- routing infra already exists
- you want sharper role specialization

### Model 3: Tool-routed orchestration
A top-level router determines task composition, then dispatches to a worker with selected modules.

Best when:
- you have orchestration around classification
- agent state can carry module choices explicitly
- complex tasks may span multiple stages or sub-agents

---

## Recommended System/Developer Split

A clean OpenAI-style setup can use:

### System-level stable content
Usually:
- `CLAUDE.md`
- possibly a compact runtime summary derived from `runtime/runtime-contract.md`

This defines:
- principles
- honesty requirements
- evidence posture
- separation discipline

### Developer/runtime-level dynamic content
Per task:
- selected behavior file(s)
- selected domain file(s)
- selected template
- selected checklist(s)
- optional stage-specific engine files

This keeps the stable system prompt small and the task context precise.

---

## Suggested Runtime Pipeline

A practical runtime pipeline is:

### Phase 1: classify
Determine:
- primary task mode
- secondary task mode if any
- relevant technologies/domains
- desired output shape

### Phase 2: compose
Load:
- kernel
- composition/runtime guidance
- selected behaviors
- selected domains
- template
- checklists

### Phase 3: execute
Follow the needed engine path:
- lightweight or full

### Phase 4: validate
Apply selected checklists as internal quality gates.

### Phase 5: deliver
Return user-facing output and optionally generate a report artifact.

---

## State Model Recommendation

If your agent runtime supports explicit state, store fields such as:

- `task_type`
- `primary_behavior`
- `secondary_behaviors`
- `domains`
- `template`
- `engine_path`
- `scope`
- `constraints`
- `evidence`
- `findings`
- `verification_status`
- `open_questions`
- `report_type` (optional)

This mirrors the repository architecture and makes execution more consistent.

---

## Template Mapping in OpenAI Systems

You can use templates in two ways.

### Option A: soft structure
Use templates as guidance for section ordering and content shape.

Best when:
- free-form natural language output is acceptable

### Option B: structured schema alignment
Map template sections to explicit output schema fields.

Example:
- `review-report.md` -> `{summary, findings[], positives, risks, next_steps}`
- `debug-report.md` -> `{symptom, evidence[], hypotheses[], root_cause, fix_options[], verification, open_questions[]}`

Best when:
- the runtime expects consistent machine-readable outputs
- results will be stored or routed programmatically

---

## Checklist Mapping in OpenAI Systems

Checklists can be used as:

### Internal self-check prompts
Before final answer, ask the model internally:
- did I separate facts from assumptions?
- is the result actionable?
- is verification clearly bounded?

### Post-generation validation pass
Run a second pass that evaluates whether the response satisfies:
- general-quality
- task-specific checklist
- delivery checklist
- verification checklist if applicable

### External evaluator layer
Use a separate evaluator agent or rule layer to apply the checklist.

This is especially strong for high-risk engineering tasks.

---

## Example Integration Patterns

### Pattern 1: Single general engineering agent

Stable:
- `CLAUDE.md`

Dynamic:
- `runtime/router.md`
- one behavior
- relevant domains
- one template
- one or more checklists

### Pattern 2: Dedicated review agent

Stable:
- `CLAUDE.md`
- `behaviors/review.md`
- `runtime/runtime-contract.md`

Dynamic:
- relevant domains
- `templates/review-report.md`
- review/delivery/verification checklists

### Pattern 3: Dedicated debug agent

Stable:
- `CLAUDE.md`
- `behaviors/debug.md`
- `runtime/runtime-contract.md`

Dynamic:
- relevant domains
- `templates/debug-report.md`
- debug/delivery/verification checklists

---

## Example Task Routing

### Input
"Review this Spring Boot + Redis code for stale cache bugs."

### Runtime composition
- behavior: review
- domains: java, spring, redis, testing
- engine path: discover -> evidence -> context -> reasoning -> verification -> delivery
- template: review-report
- checklists: general-quality, review-checklist, verification-checklist, delivery-checklist

### Input
"Why does this Playwright test fail only in CI?"

### Runtime composition
- behavior: debug
- domains: playwright, testing
- engine path: discover -> evidence -> context -> reasoning -> delivery
- template: debug-report
- checklists: general-quality, debug-checklist, delivery-checklist

---

## OpenAI-Specific Advice

### Keep stable system instructions small
Do not place the whole repository in the permanent system layer.

### Prefer runtime composition
Select modules based on task classification.

### Preserve explicit verification boundaries
Especially important when the model sounds confident by default.

### Use templates as schemas when needed
This makes downstream automation much easier.

### Consider evaluator passes
For high-stakes tasks, checklist-driven second-pass validation is worth it.

---

## Anti-Patterns

Avoid:
- monolithic system prompt that embeds every module
- no distinction between stable rules and task-specific overlays
- always-on loading of every domain
- response generation without checklist validation
- using templates only cosmetically without preserving their intent
- skipping explicit task routing

---

## Suggested Minimal OpenAI Agent Base

A strong minimal base for a dynamic agent is:

Stable:
- `CLAUDE.md`

Runtime-selected:
- `runtime/router.md`
- `runtime/runtime-contract.md`
- one behavior
- relevant domains
- one template
- relevant checklists

Optional:
- `runtime/conflict-resolution.md`
- `reports/*`
- second-pass evaluator using checklists

---

## Short Reminder

For OpenAI-style agents, this repository works best as:
- a small stable core
- a runtime-selected module graph
- optionally schema-backed output
- optionally checklist-validated delivery
