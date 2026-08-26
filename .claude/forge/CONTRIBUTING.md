# CONTRIBUTING.md

## Purpose

This repository is a modular system, not a loose collection of prompts.

Contributions should preserve:
- separation of concerns
- composability
- clarity
- maintainability
- evidence-aware engineering style

Before adding or changing content, contributors should understand the architecture and standards in this repository.

---

## Contribution Principles

### 1. Respect layer boundaries
Do not solve a problem by editing the wrong layer.

Examples:
- do not add output formatting rules into a domain file
- do not add technical framework heuristics into a template
- do not add task workflow into a behavior file

### 2. Prefer refinement over proliferation
If an existing file can be improved cleanly, prefer that over adding a new overlapping file.

### 3. Add modules only when reusable
A new module should serve repeated patterns, not one isolated scenario.

### 4. Preserve composability
Changes should make modules easier to combine, not more entangled.

### 5. Be explicit about why a change is needed
Every substantial addition should have a rationale.

---

## Before You Add a New File

Ask:

- Does this concern already belong to an existing file?
- Is this a new layer concern or just more content for an existing layer?
- Will this be reused across multiple tasks?
- Does the new file create overlap or confusion?
- Would a short section in an existing file be better?

If the answer suggests overlap, prefer updating an existing file.

---

## Contribution Types

### 1. Refinement
Examples:
- improve clarity in an existing behavior
- strengthen domain heuristics
- tighten checklist wording
- add better examples to runtime guidance

Usually preferred.

### 2. Extension
Examples:
- add a new domain for a distinct technology
- add a new template for repeated output form
- add a new checklist for recurring quality risk

Requires stronger justification.

### 3. Restructuring
Examples:
- split a bloated file
- merge overlapping modules
- clarify naming
- adjust composition guidance

Should be done carefully and documented clearly.

---

## Pull Request Expectations

A strong contribution should explain:

- what changed
- why it changed
- which layer(s) were affected
- why those layers are the right place
- whether composition behavior changes
- whether naming or governance implications exist

If adding a new file, explain:
- why current modules were insufficient
- expected reuse cases
- possible overlap and how it was avoided

---

## Content Expectations

Good contributions are:

- specific
- reusable
- scoped
- layer-correct
- non-duplicative
- aligned with existing tone and structure

Avoid changes that are:

- overly generic
- redundant
- too tailored to one narrow case
- hard to compose
- difficult to maintain

---

## Review Questions for Contributors

Before submitting, ask:

- Is this change in the right layer?
- Does it duplicate something else?
- Is the naming consistent?
- Does it improve reuse?
- Is the wording precise?
- Does it preserve system simplicity?
- Would a future contributor understand why this exists?

---

## What Not to Do

Do not:
- dump miscellaneous rules into `CLAUDE.md`
- turn behavior files into workflow engines
- turn domain files into broad tutorials
- add templates for one-off preferences
- create checklists that simply restate the entire system
- add modules without showing repeated use need

---

## Documentation Expectations

If you add:
- a new behavior
- a new domain
- a new template
- a new runtime/meta file

you should also update any relevant:
- architecture notes
- naming documentation
- change policy references
- module selection examples if composition meaningfully changes

---

## Short Reminder

Contribute by:
- preserving layer boundaries
- improving reuse
- avoiding overlap
- explaining rationale
- keeping the system maintainable
