---
name: explore
description: >-
  Pre-orientation exploration mode — scope discovery, option enumeration,
  situation assessment, and problem-space mapping before committing to a
  specific task mode (plan, debug, refactor, document, etc.).
  Use when the user says: explore, investigate options, scoping, discovery,
  recon, look into, 先看看, 先分析下情况, 先摸清楚, 先调研一下, 先探索一下,
  帮我梳理一下, 先盘点一下, 先看下现状, 先别急着实现.
  For any request where the user is not yet sure how to classify the task.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
---

# Explore

## 1. Purpose

Explore is a **pre-orientation mode** — it helps the user understand the problem
space before committing to a specific task mode. It does not rush to conclusions,
fixes, or implementation plans.

When a user asks to inspect the situation before choosing an action, the correct response
is exploration, not a premature plan or diagnosis.

## 2. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Detect technical domains from codebase context:
   - Java project → `.claude/forge/domains/java.md`
   - Spring annotations → `.claude/forge/domains/spring.md`
   - Database/SQL → `.claude/forge/domains/mysql.md`
   - Cache/Redis → `.claude/forge/domains/redis.md`
   - Test code → `.claude/forge/domains/testing.md`
   - Playwright → `.claude/forge/domains/playwright.md`
   - Spring AI → `.claude/forge/domains/spring-ai.md`
   - If no clear domain signal, skip domain loading.
3. Execute blocked_task workflow: discover → evidence → context → delivery
4. Use `template.exploration` — structured but lightweight, scannable output
5. Apply `checklist.general_quality` + `checklist.delivery`

## 3. Core Discipline

### When to use explore
- The user hasn't clearly stated what kind of task they need
- The problem space is unknown or poorly bounded
- The user wants to understand options before committing
- There are multiple possible directions and no clear winner
- Requests to inspect, research, or map the current situation first

### What explore does
1. **Discover** — frame what the user is really asking, clarify ambiguity
2. **Evidence** — collect facts from code, config, logs, repo structure
3. **Context** — map the landscape: what exists, what's connected, what's at stake
4. **Delivery** — present findings, enumerate viable directions, recommend next step

### What explore does NOT do
- Does NOT jump to root cause (that's `debug`)
- Does NOT propose implementation steps (that's `plan`)
- Does NOT produce a formal report structure (that's `report`)
- Does NOT explain a known concept (that's `explain`)
- Does NOT commit to structural changes (that's `refactor`)

## 4. Output Structure

Exploration output should be lightweight and scannable:

```
## Current Understanding
  - What the user is asking (clarified)
  - What is known
  - What is still unknown

## Landscape
  - Relevant modules / services / components
  - Key relationships and dependencies
  - Scope boundaries

## Observations
  - What stands out (structured, not judgmental)
  - Patterns, surprises, gaps

## Possible Directions
  - Option A: <what it would look like, when it fits>
  - Option B: ...
  - Option C: ...

## Recommended Next Step
  - Suggested task mode: review / debug / plan / refactor / ...
  - What additional information would help
  - One concrete action
```

## 5. Boundary with Other Skills

| User says | Use |
|-----------|-----|
| "Inspect the situation first" | **explore** |
| "What is the root cause of this bug?" | **debug** |
| "Give me an implementation plan" | **plan** |
| "Explain how this mechanism works" | **explain** |
| "Refactor this class" | **refactor** |
| "How should this feature be implemented?" | **plan** |
| "Write the documentation" | **document** |

When exploration reveals that the task is actually better served by another skill,
explicitly tell the user: "This now looks like a **[skill]** task — switch modes?"

## 6. Guard

Before delivering:
- [ ] User intent clarified (not assumed)
- [ ] Landscape mapped at appropriate depth
- [ ] Options enumerated, not prematurely narrowed
- [ ] Recommended next step is concrete and actionable
- [ ] If exploration reveals the task fits another skill, that's noted
- [ ] **Output**: Default to inline display. Do not write to file unless the user explicitly requests it.
