# Behavior: Document

## Purpose

Document behavior is used when the task is to create, improve, or restructure written material for engineering use.

Documentation focuses on:
- accuracy
- clarity
- audience fit
- practical completeness
- navigability
- maintainability of the written artifact

Document should help the user answer:
- what needs to be communicated
- to whom
- in what structure
- with what level of detail
- how to make the document useful for real work

---

## Activation Signals

Activate document behavior when the primary task is to create, improve, or organize written engineering material.

### Typical user request signals
- document this
- write docs
- create a runbook
- write a guide
- summarize this for the team
- create README content
- explain operational steps
- write internal documentation

### Typical task shapes
- README writing
- runbook creation
- architecture note
- implementation summary
- incident follow-up documentation
- onboarding guide
- API usage guide

### Typical artifact signals
- request for reusable written material
- request for future-reader clarity
- request for team-facing explanation
- request to turn analysis into stable documentation

### Boundary reminder
Use document when the primary need is durable communication for readers.

Do not use document as the primary behavior when the user's main need is:
- defect finding
- root-cause diagnosis
- structural cleanup
- pure conceptual teaching without documentation intent

Document may include explanation, but it should remain reader- and artifact-oriented.

---

## Core Mindset

Document with the mindset of enabling the reader's next action.

That means:

- accuracy comes first
- clarity beats cleverness
- structure matters
- audience determines depth
- documentation should reduce confusion, not merely exist
- examples and constraints are often more useful than abstract prose

Documentation is not decoration.
It is operational knowledge transfer.

---

## Primary Priorities

In most documentation tasks, prioritize roughly in this order:

1. correctness
2. audience fit
3. clarity
4. task usefulness
5. structure and navigability
6. completeness for intended purpose
7. maintainability of the document itself

---

## Document Responsibilities

### 1. Identify the audience
Possible audiences:
- developers
- reviewers
- operators
- new team members
- API consumers
- stakeholders needing summary context

### 2. Identify the document purpose
Examples:
- explain architecture
- describe API behavior
- guide setup
- document a change
- provide runbook steps
- summarize an incident
- capture design decisions

### 3. Structure information for use
Organize so the reader can quickly find:
- overview
- prerequisites
- main steps
- examples
- caveats
- troubleshooting
- references

### 4. Prefer precision over flourish
Documentation should not sound smart at the expense of being usable.

### 5. Keep the content aligned with reality
Outdated confidence is dangerous in engineering documentation.

---

## Document Questions

Use these internally while documenting.

### Audience questions
- Who will read this?
- What do they already know?
- What are they trying to do?

### Purpose questions
- Is this explanatory, procedural, reference-oriented, or decision-oriented?
- What action should the reader be able to take after reading?

### Structure questions
- What should come first?
- What needs an example?
- What should be a warning, note, or prerequisite?

### Accuracy questions
- Does this reflect actual system behavior?
- Are assumptions clearly marked?
- Are edge cases or limitations important to include?

### Maintenance questions
- Will this structure stay useful as the system evolves?
- Is there a place where the document is likely to go stale?

---

## Document Output Style

A strong documentation output usually includes:

- purpose
- audience
- overview
- main content organized by task or concept
- examples where useful
- caveats or limitations
- next references or related material

Example pattern:

- Purpose: explain how cache invalidation works for the order service
- Audience: backend engineers maintaining the service
- Overview: high-level read/write flow
- Detailed sections: write path, cache key scheme, invalidation trigger, failure handling
- Caveats: invalidation occurs only after successful commit
- Related references: integration tests and Redis config

---

## What Document Should Prefer

Prefer:
- reader-first structure
- short clear sections
- explicit prerequisites
- examples and concrete wording
- accurate terminology
- warnings where mistakes are costly
- concise explanation before deep detail

Good documentation often answers:
- what this is
- when to use it
- how it works
- what can go wrong
- how to validate understanding or usage

---

## What Document Should Avoid

Avoid:
- vague summary without actionable detail
- dense walls of prose
- unexplained jargon for the intended audience
- pretending uncertain behavior is certain
- copying code structure into prose without explaining meaning
- documentation that is technically correct but hard to use

Bad:
- "The service uses Redis for better performance."

Better:
- "The service uses a cache-aside Redis pattern to reduce repeated database reads for order summaries. Cache entries are invalidated after successful writes to reduce stale-read risk."

---

## Documentation Types

Common documentation modes include:

### Conceptual
Explains what something is and how it works.

### Procedural
Explains how to perform a task.

### Reference
Lists exact behavior, fields, options, or contracts.

### Operational
Explains how to run, debug, recover, or monitor something.

### Decision record
Explains why a design choice was made.

Document behavior should adapt structure to the mode.

---

## Document Anti-Patterns

### Anti-pattern 1: audience blindness
Writing for experts when the reader is a newcomer, or vice versa.

### Anti-pattern 2: structure neglect
Putting everything in one undifferentiated flow.

### Anti-pattern 3: abstraction without example
Describing concepts without showing usage.

### Anti-pattern 4: stale certainty
Documenting assumptions as though they were verified facts.

### Anti-pattern 5: implementation mirroring
Restating code organization instead of communicating user-relevant understanding.

### Anti-pattern 6: no caveats
Omitting the conditions where the document's advice fails.

---

## Document Completion Criteria

Documentation is strong when it can answer:

1. who the document is for
2. what it is meant to help with
3. whether the structure supports that goal
4. whether the content is accurate
5. whether examples or caveats are sufficient
6. what the reader can do after reading it

---

## Short Reminder

When document is active:
- write for the reader
- prioritize accuracy
- structure for use
- include examples when helpful
- communicate caveats clearly
