# Standard: Versioning

## Purpose

This document defines a lightweight versioning approach for the repository.

The goal is not heavy release ceremony.
The goal is to make structural changes understandable over time.

---

## Versioning Principles

### 1. Version the repository as a system
Changes to the modular operating model may affect how tasks are composed or interpreted.
Track those changes intentionally.

### 2. Treat structural changes as meaningful
A new behavior, a split domain, or a changed template contract may alter system use and should be version-visible.

### 3. Prefer compatibility when possible
Stable module names and stable responsibilities reduce migration cost.

---

## Suggested Version Semantics

Use a simple semantic-style approach:

- MAJOR: architectural or compatibility-breaking changes
- MINOR: new modules or meaningful capability expansion
- PATCH: wording improvements, clarifications, examples, and non-breaking refinements

### Examples

#### MAJOR
- renaming widely used modules
- changing layer responsibilities
- removing or merging foundational files
- changing composition logic in a way that breaks existing usage assumptions

#### MINOR
- adding a new domain
- adding a new template
- adding a new checklist
- expanding runtime guidance with new reusable capability

#### PATCH
- clarifying wording
- improving examples
- tightening checklist questions
- refining domain heuristics without changing module role

---

## Change Log Expectations

For meaningful changes, record:

- what changed
- why it changed
- affected layer(s)
- compatibility impact
- whether examples or standards were updated

A lightweight changelog is enough.

---

## Backward Compatibility Guidance

Try to preserve:
- stable file names
- stable layer responsibilities
- stable template intent
- stable checklist meaning

If breaking compatibility:
- explain why
- document migration impact
- update affected examples and standards

---

## Short Reminder

Versioning should reflect:
- structural impact
- compatibility impact
- capability growth
- not just file count changes
