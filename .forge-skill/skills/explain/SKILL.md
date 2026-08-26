---
name: explain
description: >-
  Explain concepts, mechanisms, tradeoffs, frameworks, architecture patterns,
  code paths, and technical decisions with progressive depth, mental-model
  building, examples, and common-misconception surfacing using forge's
  domain-aware explain behavior.
  Use when the user says: explain this, how does this work, why does this happen,
  what is the difference between, help me understand, walk me through this,
  can you clarify, teach me, what is, what are, tell me about, describe how,
  I want to understand,
  解释, 讲解, 说明一下, 帮我理解, 这是怎么工作的, 有什么区别, 教我, 介绍.
  For any concept explanation request that benefits from structured,
  domain-informed clarification.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
---

# Explain

## 1. Activation Sequence

1. Load forge kernel: `.forge-skill/forge/CLAUDE.md`, `.forge-skill/forge/AUTOLOAD.md`
2. Identify the concept, mechanism, or tradeoff to explain
3. Detect technical domains from the topic:
   - Spring concepts → `.forge-skill/forge/domains/spring.md`
   - Java language/runtime → `.forge-skill/forge/domains/java.md`
   - Database topics → `.forge-skill/forge/domains/mysql.md`
   - Cache topics → `.forge-skill/forge/domains/redis.md`
   - Testing topics → `.forge-skill/forge/domains/testing.md`
   - If no domain matches the topic, skip domain loading. Explain with general knowledge only. Note unapplied domains.
4. Compose forge modules per section 2
5. Execute explanation workflow
6. Deliver structured explanation

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.forge-skill/forge/behaviors/explain.md` | Primary: concept clarification, mental model building |
| Domains | Detected from topic | Domain-specific context and examples |
| Template | `.forge-skill/forge/templates/explanation.md` | Output: what → why → how → example → pitfalls |
| Checklists | `.forge-skill/forge/checklists/general-quality.md`, `.forge-skill/forge/checklists/delivery-checklist.md` | |
| Workflow | `workflow.light_explanation` | Lightweight: discover → context → reasoning → delivery |

## 3. Core Discipline (from explain.md)

### Progressive Depth Pattern
1. **What it is** — concise definition (1-2 sentences). The reader should understand the concept at a high level immediately.
2. **Why it matters** — practical significance. When does this matter in real engineering work? What problem does it solve?
3. **How it works** — mechanism in logical order. Walk through the key steps or components. Use concrete examples tied to real code.
4. **Example** — a concrete, minimal example that illustrates the concept in action. Prefer code that could actually run.
5. **Common pitfalls / misconceptions** — what do people usually get wrong about this? What are the edge cases that surprise engineers?
6. **Deeper detail** (optional) — progressive depth for those who want more. Only add if the user asks or the topic warrants it.

### Quality Standards
- **Jargon-second**: introduce the concept in plain language first, then give the technical term
- **Accuracy over simplicity**: do not distort correctness for an easier explanation
- **Mental model**: help the user build a reusable mental model, not just memorize facts
- **Concrete over abstract**: prefer specific examples over vague descriptions
- **Connect to known concepts**: relate new ideas to what the user likely already knows

### Anti-Patterns
- Jargon-first explanation that assumes prior knowledge
- Excessive detail before the main idea lands
- Shallow analogies that distort correctness ("it's like a pizza delivery...")
- Code restatement without interpretation
- Domain-specific details without domain context

## 4. Output Structure

```
## What Is <concept>?
<1-2 sentence plain-language definition>

## Why It Matters
<practical significance in real engineering>

## How It Works
<mechanism in logical order, with code references where helpful>

## Example
<concrete, minimal, runnable if possible>

## Common Pitfalls
<what engineers usually get wrong, edge cases, surprises>

## Deeper Detail (if needed)
<progressive depth for those who want more>
```

## 5. Guard

- [ ] Definition is clear and jargon-second
- [ ] Practical significance explained
- [ ] Example is concrete and relevant
- [ ] Common pitfalls surfaced
- [ ] Domain context applied if domain loaded
- [ ] No distortion of correctness for simplicity
