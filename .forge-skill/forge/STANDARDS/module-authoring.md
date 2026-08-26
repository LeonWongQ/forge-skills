# Standard: Module Authoring

## Purpose

This document defines how to write new modules consistently.

A good module should be:
- focused
- composable
- clear
- non-overlapping
- maintainable

This standard applies to:
- engine files
- behavior files
- domain files
- template files
- checklist files
- report files

---

## Core Authoring Rules

### 1. One file, one responsibility
A module should solve one kind of problem.

### 2. Write to the layer
Author the file according to its layer role.

- engine = process/stage logic
- behavior = judgment mode
- domain = technical expertise
- template = output shape
- checklist = quality gate
- report = persistent artifact structure

### 3. Avoid cross-layer leakage
Do not embed another layer's responsibility unless a small reference is necessary for clarity.

### 4. Favor reusable language
Write for repeated use, not one narrow case.

### 5. Keep examples illustrative, not exhaustive
Examples should clarify intent without turning the file into a tutorial catalog.

---

## Recommended File Shape

Most modules should contain some version of:

1. Purpose
2. Scope or focus
3. Core rules / responsibilities
4. Good-use guidance
5. Anti-patterns or limits
6. Short reminder

Not every file needs every section, but this is the preferred shape.

---

## Writing Style

Use language that is:

- direct
- precise
- operational
- reusable
- evidence-aware

Avoid language that is:

- vague
- over-decorative
- overly conversational inside standards files
- tied to one transient incident
- redundant with higher-level principles

---

## Good Module Qualities

A strong module is:

- understandable in isolation
- easy to combine with others
- clearly different from nearby modules
- scoped tightly enough to stay coherent
- broad enough to justify existing

---

## Bad Module Qualities

A weak module is:

- mostly duplicative
- conceptually mixed
- too narrow to reuse
- too broad to stay precise
- dependent on other files for basic coherence
- acting as a dumping ground

---

## Authoring by Layer

### Engine files
Should define:
- purpose of the stage
- inputs
- outputs
- required questions
- completion criteria
- common failure modes

Should not define:
- specific technology heuristics
- review/debug-specific priorities unless only as examples

### Behavior files
Should define:
- mindset
- priorities
- what to focus on
- what to avoid
- output tendencies

Should not define:
- full workflow
- technology details
- template sections

### Domain files
Should define:
- relevant technical concerns
- common failure modes
- review/debug heuristics
- verification hints
- domain-specific limits

Should not define:
- process flow
- universal principles
- final formatting rules

### Template files
Should define:
- output purpose
- sections
- section guidance
- good-fit cases
- avoid cases

Should not define:
- technical reasoning content
- workflow

### Checklist files
Should define:
- clear review questions
- pass/fail style quality gates
- failure signals

Should not become:
- essays
- duplicate architecture files
- substitute workflow logic

### Report files
Should define:
- persistent record structure
- intended reuse context
- section purpose
- concise archival guidance

---

## Naming and Section Consistency

When possible, use consistent headings such as:

- Purpose
- Focus / Scope
- Responsibilities
- Questions
- Guidance
- Anti-Patterns
- Completion Criteria
- Short Reminder

Consistency improves usability.

---

## Splitting and Merging Rules

### Split a file when
- it has more than one distinct responsibility
- it has become hard to navigate
- multiple sections could stand alone as reusable modules

### Merge files when
- two files overlap heavily
- contributors cannot reliably tell which one to use
- distinctions are artificial rather than useful

Do not split simply to increase file count.

---

## Short Reminder

Write modules that are:
- layer-correct
- focused
- reusable
- clear
- maintainable
