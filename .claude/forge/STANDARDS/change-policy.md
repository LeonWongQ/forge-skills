# Standard: Change Policy

## Purpose

This document defines how repository changes should be evaluated.

The goal is to keep the system:
- coherent
- maintainable
- extensible without bloat
- stable enough for repeated use

---

## Change Evaluation Questions

Before accepting a meaningful change, ask:

1. What problem does this change solve?
2. Why is the current repository insufficient?
3. Which layer should own this change?
4. Does this change overlap with an existing module?
5. Is the new complexity justified by reuse value?
6. Does this improve composability or weaken it?
7. Does it create naming or architectural confusion?
8. Does it require updates to standards or examples?

---

## Allowed Change Categories

### 1. Clarification
Improves wording, examples, or precision without changing architecture.

Usually low risk.

### 2. Capability expansion
Adds a reusable module or major section.

Requires justification and layer-fit review.

### 3. Structural change
Moves responsibilities, renames modules, merges/splits files, or changes composition patterns.

Requires strongest scrutiny.

---

## Acceptance Criteria

A good change should be:

- layer-correct
- reusable
- non-duplicative
- clear in purpose
- maintainable
- compatible where reasonably possible

---

## Reasons to Reject or Rework a Change

Reject or revise if the change:

- duplicates an existing module
- blurs layer boundaries
- adds complexity without repeated-use value
- is too specific to one niche case
- makes naming less clear
- forces broader architectural inconsistency
- encourages bloated outputs by default

---

## Change Impact Levels

### Low impact
- wording fixes
- examples
- small refinements

### Medium impact
- new sections in existing files
- new checklist/template/domain where reuse is clear

### High impact
- kernel edits
- engine restructuring
- major naming changes
- behavior boundary changes
- removal/merge of core modules

High-impact changes should be especially well-justified.

---

## Governance Preference

When two changes are both workable, prefer the one that:

- preserves simpler architecture
- keeps modules more distinct
- improves reuse with less coupling
- avoids introducing a new file unless necessary

---

## Short Reminder

Change policy means:
- solve a real repeated problem
- put the change in the right layer
- prefer refinement before proliferation
- reject bloat
