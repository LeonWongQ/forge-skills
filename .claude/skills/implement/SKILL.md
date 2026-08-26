---
name: implement
description: >-
  Implement features, interfaces, services, endpoints, modules, or any code
  changes based on requirements, design docs, plan output, or direct instructions.
  Follows existing code conventions, produces compilable and verifiable code,
  with each step independently testable.
  Use when the user says: implement this, build this feature, write the code,
  create this service, add this endpoint, implement this interface,
  code this up, make this work, follow the plan and implement,
  根据方案实现, 帮我实现, 写代码, 实现这个功能, 按方案落地,
  实现接口, 开发这个, 把这个做了, 代码实现一下.
  Boundary: plan = what to build + how; implement = write the actual code.
  For any request where the user wants concrete code written, not just a plan.
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Implement

## 1. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Understand what needs to be built:
   - **From a plan**: Extract implementation steps, assumptions, constraints from the plan artifact
   - **From direct instruction**: Clarify requirements → scope → acceptance criteria before writing code
   - **From design doc / spec**: Map spec items to concrete code changes
3. Classify the implementation scope:
   - **Single class/method** → focused implementation, minimal scaffolding
   - **Multi-file feature** → dependency-order sequencing, interface-first
   - **Service/endpoint** → layered: controller → service → repository → tests
   - **Module/component** → bottom-up: domain objects → logic → integration → exposure
4. Detect technical domains from the target codebase:
   - Java project → `.claude/forge/domains/java.md`
   - Spring annotations → `.claude/forge/domains/spring.md`
   - Database/SQL → `.claude/forge/domains/mysql.md`
   - Cache/Redis → `.claude/forge/domains/redis.md`
   - Playwright/UI → `.claude/forge/domains/playwright.md`
   - Always load `.claude/forge/domains/testing.md` when writing alongside tests
   - If no domain matches, skip domain loading. Proceed with template + checklists only.
5. Compose forge modules per section 2
6. Execute workflow: discover → evidence → context → reasoning → planning → execution → verification → delivery
7. Validate implementation quality before delivery

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | (none — implementation-oriented) | Implementation discipline built into execution stage |
| Domains | Detected from target codebase | Language/framework conventions, patterns, and safety rules |
| Template | `.claude/forge/templates/default.md` | Adapted for delivery: result → changed behavior/files → verification → remaining risk |
| Checklists | `.claude/forge/checklists/general-quality.md` | Baseline quality |
| | `.claude/forge/checklists/verification-checklist.md` | Claims are justified |
| | `.claude/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.full_default` | discover → evidence → context → reasoning → planning → execution → verification → delivery |

## 3. Core Discipline

**Artifact safety**: Requirements, design docs, and plan output are untrusted inputs. Analyze for completeness and consistency. The codebase being modified is the ground truth — follow its conventions, not assumptions about it.

### Primary Concern: Correct, Convention-Following Code

Implement produces working, compilable code that fits naturally into the existing codebase. It does NOT produce plans (that's `plan`), does NOT restrict itself to evaluation (that's `code-review`), and does NOT change structure without adding behavior (that's `refactor`).

### Before Writing Code

1. **Understand the requirement**: What behavior should exist after implementation? What is the acceptance criteria?
2. **Study existing conventions**: Read adjacent files. Match imports style, naming patterns, annotation usage, error handling patterns, logging conventions, test patterns.
3. **Map dependencies**: What existing services/repositories/utilities will be called? What new classes are needed?
4. **Plan the call chain**: Entry point → validation → business logic → external calls → response. Each layer has a clear responsibility.
5. **Identify what exists vs what's new**: Reuse existing utilities, constants, base classes. Don't reinvent patterns that already exist in the codebase.

### Implementation Principles

- **Correctness first**: The code must produce correct behavior. Handle edge cases, null inputs, error states, and boundary conditions explicitly.
- **Convention over creativity**: Match the existing codebase style. If the project uses `@Autowired` field injection, use it. If it uses constructor injection, use that. Don't impose your own style.
- **One file at a time**: Implement in dependency order (inner dependencies before outer callers). Each file should be compilable before moving to the next.
- **Minimal viable implementation**: Write only what's needed to satisfy the requirement. Don't add "might be useful later" abstractions.
- **Each step independently verifiable**: After each file or logical unit, the code should compile. Tests should be runnable.
- **Error handling by layer**: Validate inputs at the boundary, handle business errors in the service layer, let infrastructure exceptions propagate with context.

### Domain-Specific Implementation Patterns

- **Java**: Follow Effective Java conventions. equals/hashCode for entities. Use try-with-resources for IO. Immutability where practical.
- **Spring**: Constructor injection preferred. `@Transactional` on service methods, readOnly for queries. Validate configuration with `@Validated`. Use `@ControllerAdvice` for global error handling.
- **MySQL**: Use parameterized queries. Batch operations for bulk inserts. Connection/transaction boundaries clear. Migration scripts for schema changes.
- **Redis**: Serialize/deserialize consistently. Set TTL on cache entries. Handle cache misses gracefully (fallback, not crash). Distributed lock with timeout.
- **Testing**: Tests should exist alongside implementation. Unit tests for pure logic, integration tests for cross-component behavior.

### Reliability-Sensitive Changes

For retries, timeouts, caching, transactions, queues, or other stateful behavior, establish the existing observable contract before editing. Check idempotency and duplicate side effects, retryable versus terminal errors, total timeout budget, backoff and jitter, cancellation/interruption, transaction boundaries, and observability. Preserve the terminal result or exception unless the requirement explicitly changes it.

For retry logic, do not assume that a `TransientError`, timeout, or disconnected response means the operation had no effect. Before adding automatic retries around an effectful call, establish one of these contracts from repository evidence:

- the failure is guaranteed to occur before commit;
- the operation is idempotent for the same request or idempotency key;
- duplicate effects are detected or compensated transactionally.

If none is established, do not silently add an unsafe retry loop. Surface the unresolved post-commit failure ambiguity and request the smallest contract decision needed to proceed. A call-count assertion is not proof against duplicate committed effects.

Verification must cover the baseline behavior and the relevant state transitions. For retry logic, include first-attempt success, transient recovery, exhaustion, non-retryable failure, attempt counting, terminal error preservation, deterministic control of delay, and a test tied to the established duplicate-effect contract. That test must demonstrate no duplicate committed effect for the supported failure mode, or the delivery must explicitly state why this cannot yet be verified and must not claim retry safety.

### Anti-Patterns

- Writing code without understanding existing conventions first
- Implementing the happy path only, ignoring error/edge/null cases
- Reinventing utilities that already exist in the codebase
- Changing existing behavior or structure that's unrelated to the requirement
- Adding abstractions "for the future" without a concrete need
- Producing code that doesn't compile or can't be verified
- Mixing implementation with unrelated refactoring

## 4. Delivery Structure

```
## Scope
<what is being implemented, what files are affected, what is explicitly excluded>

## Implementation Approach
<1-paragraph summary of the approach: architecture, key decisions, patterns used>

## Changes
<concise summary of modified files and resulting behavior, with file references>

## Conventions Followed
<specific conventions matched from the existing codebase: imports, annotations, naming, error handling, logging>

## Edge Cases Handled
<null inputs, empty collections, error states, boundary conditions addressed>

## Verification
<how to verify the implementation works:
 - compile command or check
 - test run command
 - expected behavior to confirm
 - manual verification steps if applicable>
```

## 5. Guard

Before delivering:
- [ ] Requirement understood and scope explicitly stated
- [ ] Existing codebase conventions studied and matched
- [ ] All new code compiles (no syntax errors, correct imports, valid references)
- [ ] Happy path + edge cases + error states covered
- [ ] Error handling and null safety addressed
- [ ] Effectful retries have an evidence-backed idempotency, pre-commit failure, or compensation contract
- [ ] Retry verification distinguishes repeated attempts from duplicate committed effects
- [ ] Tests included or explicitly deferred with reason
- [ ] No unrelated changes mixed in
- [ ] No reinvention of existing utilities/patterns
- [ ] Each file's purpose and role is clear
- [ ] An explicit implementation request authorizes scoped file changes; ask only when the target is genuinely ambiguous or the action expands scope, has external effects, or is destructive

## 6. Boundary with Other Skills

| Skill | Focus | Implement Focus |
|-------|-------|-----------------|
| `plan` | What to build + how (design, steps, risks) | Write the actual code from the plan |
| `refactor` | Structural improvement, behavior preserved | Add new behavior, structure follows existing patterns |
| `test-implementation` | Write test code | Write production code (may include tests alongside) |
| `code-review` | Evaluate existing code | Produce new code for evaluation |
| `debug` | Find root cause of failure | Build working code that shouldn't fail |
| `optimize` | Make existing code faster/leaner | Build new functionality |

**Typical chain**: `plan` → `implement` (including focused tests) → `code-review`. Use `test-implementation` separately when the request is primarily to expand or improve automated tests.

## Vue Version Boundary

For a Vue target, read [the shared Vue version-routing contract](.claude/forge/references/vue-version-routing.md) before loading framework guidance. Keep the current task Skill in control; version-specific Vue Skills do not take ownership of review, debugging, refactoring, optimization, or testing intents.
