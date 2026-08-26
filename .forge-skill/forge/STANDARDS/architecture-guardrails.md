# Standard: Architecture Guardrails

## Purpose

This document protects the modular architecture from drift, overlap, and sprawl.

The goal is to preserve:
- clear layer boundaries
- composability
- maintainability
- low duplication
- stable mental models

This document is intentionally strict.
It exists to prevent slow architectural erosion.

---

## Guardrail 1: Engine files define workflow stages only

Files in `/engine` must define:
- stage purpose
- stage inputs
- stage outputs
- stage completion criteria
- stage-specific failure modes

Files in `/engine` must not become:
- example collections
- integration guides
- domain tutorials
- output templates
- policy dumping grounds

If a file is not a workflow stage, it should not live in `/engine`.

---

## Guardrail 2: Runtime files define orchestration only

Files in `/runtime` define:
- task routing
- runtime composition
- conflict handling
- execution contract

They must not replace engine stages.
They must not absorb domain heuristics or template logic.

---

## Guardrail 3: Behavior files define judgment mode only

Files in `/behaviors` define:
- priorities
- attention focus
- evaluation style
- what success means for that task mode

They must not define:
- workflow sequencing
- technical deep-dives specific to a technology
- final report section structure

---

## Guardrail 4: Domain files are heuristic guides, not full references

Files in `/domains` define:
- task-relevant technical concerns
- common failure modes
- specialized review/debug hotspots
- verification hints

They must not become:
- full tutorials
- encyclopedic references
- framework manuals
- dumping grounds for every known best practice

A domain file should help judgment, not replace official documentation.

---

## Guardrail 5: Template files define output structure only

Files in `/templates` define:
- final output shape
- section ordering
- section intent
- fit / non-fit guidance

They must not define:
- technical reasoning rules
- workflow
- domain logic
- large example catalogs

---

## Guardrail 6: Checklist files define quality gates only

Files in `/checklists` define:
- review questions
- pass/fail style checks
- failure signals

They must not become:
- essays
- architecture descriptions
- substitute workflows
- duplicate templates

---

## Guardrail 7: Report files should stay few and stable

Files in `/reports` define persistent artifacts.
They should remain:
- high-value
- reusable
- few in number

Do not create a new report type for every new task flavor.
A report type must justify itself through repeated reuse.

---

## Guardrail 8: Example content belongs in onboarding docs, not workflow core

Examples should live in:
- `EXAMPLES.md`
- integration docs
- onboarding docs

Examples should not be distributed across core workflow files unless minimal examples are truly needed for clarity.

---

## Guardrail 9: New modules must justify their layer

Before adding a new file, answer:

1. Which layer owns this concern?
2. Why is no existing file sufficient?
3. Will this be reused?
4. Does this reduce ambiguity or increase it?
5. Will future contributors know when to use it?

If those answers are weak, do not add the file yet.

---

## Guardrail 10: Prefer refinement before proliferation

When a problem appears, prefer this order:

1. clarify an existing file
2. add a section to an existing file
3. split or merge overlapping files
4. add a new file only if reuse is clear and boundaries stay sharp

File count growth is not a success metric.

---

## Sprawl Triggers

A module should be reviewed for split, merge, or rewrite when:

- it no longer has one clear responsibility
- it heavily duplicates nearby files
- contributors repeatedly choose the wrong file
- it becomes hard to explain in one sentence
- it tries to solve both policy and workflow
- it grows mostly by examples rather than reusable rules

---

## Preferred Responses to Growth

### If a file becomes too broad
- split by responsibility, not by arbitrary size

### If two files overlap
- merge or sharply redefine boundaries

### If a layer accumulates many "support" files
- separate core from support explicitly

### If examples grow faster than rules
- move examples into onboarding or examples docs

---

## Anti-Patterns

Avoid:

- adding "misc" or "general" files as dumping grounds
- creating modules for one-off scenarios
- copying the same rule into multiple layers
- turning domain files into training material
- turning behavior files into pseudo-workflows
- letting integration docs define architecture

---

## Enforcement Questions

During review, ask:

- Is this file in the right directory?
- Does it have one responsibility?
- Does it duplicate another file?
- Is it reusable?
- Is it making the architecture clearer?
- Would a future maintainer know why it exists?

---

## Short Reminder

Architecture guardrails mean:
- keep layers pure
- resist sprawl
- prefer refinement
- add modules only when reuse is real
