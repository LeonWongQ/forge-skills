# Packs

## Purpose

This directory contains precomposed task packs built from the modular repository.

A pack is a reusable task composition that bundles:

- kernel expectations
- runtime guidance
- one or more behaviors
- one or more domains
- a workflow
- a template
- checklists
- optional report recommendations

Packs are designed to reduce assembly overhead for common engineering tasks.

---

## Why Packs Exist

The repository is modular by design.
That is powerful, but it can introduce assembly cost for repeated task types.

Packs solve this by providing ready-made compositions for common scenarios.

Examples:
- Spring service review
- Playwright flaky test diagnosis
- Redis stale-read incident analysis
- Java refactor planning

A pack should make it easier to answer:
- what should I load?
- what workflow should I use?
- what output shape should I expect?

---

## What a Pack Contains

A pack usually contains:

- `id`
- `name`
- `purpose`
- `when_to_use`
- `modules`
- `workflow`
- `template`
- `checklists`
- `reports` (optional)
- `notes` (optional)

---

## Relationship to Other Layers

### Relationship to `/runtime`
Packs do not replace routing.
They provide predefined compositions that the runtime may select directly when the task strongly matches a known scenario.

### Relationship to `/registry/compositions.json`
Compositions define reusable composition metadata.
Packs define ready-to-use operational bundles.

A composition is a routing pattern.
A pack is a concrete reusable loadout.

### Relationship to `/templates`
A pack chooses a default output shape.

### Relationship to `/reports`
A pack may recommend a persistent report artifact when the task often benefits from one.

---

## When to Create a New Pack

Create a new pack only when:
- the task type is common
- the composition is stable
- repeated manual assembly would be wasteful
- the pack improves speed without hiding important choices

Do not create packs for one-off scenarios.

---

## Current Pack Philosophy

Packs should remain:

- few
- high-value
- understandable
- easy to select
- grounded in real repeated task shapes

This is not meant to become a giant catalog of every possible use case.

---

## Example Pack Categories

Common pack categories include:

- code review packs
- debugging packs
- refactor packs
- incident packs
- documentation/runbook packs
- test analysis packs

---

## Short Reminder

A pack is a reusable task bundle.

It is the fastest way to apply this repository to a repeated engineering scenario.
