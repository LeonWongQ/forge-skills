# GETTING-STARTED.md

## Purpose

This guide explains how to start using the repository in practice.

It is written for:
- humans manually composing prompts
- agent builders
- teams integrating the repository into tooling
- contributors trying to understand the minimum useful flow

You do not need to load every file for every task.
The system is modular by design.

---

## Quick Start

For a first usable setup, think in five steps:

1. load the kernel
2. identify the task mode
3. identify the technical domain
4. run the right engine path
5. shape the result with a template and checklist

Minimum conceptual flow:

```text
CLAUDE.md
  -> composition
  -> behavior(s)
  -> domain(s)
  -> engine stages
  -> template
  -> checklist(s)
```

---

## Minimal Viable Run

If you want to try the system with the smallest useful setup, start here.

You do **not** need the full repository for a first successful run.

A minimal viable setup is:

- `CLAUDE.md`
- one behavior file
- one domain file
- one template
- one checklist

Example minimal set:

- `CLAUDE.md`
- `behaviors/review.md`
- `domains/java.md`
- `templates/default.md`
- `checklists/general-quality.md`

This is enough to perform a lightweight Java code review with:
- global principles
- one task mode
- one technical lens
- one output shape
- one baseline quality gate

### Minimal Workflow

Use this simple flow:

1. understand the task
2. apply the behavior lens
3. apply the domain lens
4. produce a concise structured answer
5. run a lightweight quality check

In practice, that means:

```text
CLAUDE.md
  -> behavior
  -> domain
  -> default template
  -> general quality checklist
```

### Example Use Case

User request:
"Review this Java method and tell me if there are any correctness issues."

Minimal composition:

- `CLAUDE.md`
- `behaviors/review.md`
- `domains/java.md`
- `templates/default.md`
- `checklists/general-quality.md`

Expected result:
- direct answer
- top finding(s)
- brief reasoning
- one recommended next step if useful

### When to Expand Beyond Minimal

Add more modules when:

- the task involves frameworks or infrastructure
- the task is diagnosis-heavy
- the task needs formal output
- verification matters strongly
- multiple technical domains materially affect the answer

Examples:

- add `domains/spring.md` for transaction or DI behavior
- add `behaviors/debug.md` for root-cause investigation
- add `templates/review-report.md` for richer structured findings
- add `checklists/verification-checklist.md` for correctness-sensitive claims
- add engine stages explicitly for deeper workflow control

### Minimal Does Not Mean Careless

Even in a minimal run:

- keep facts separate from assumptions
- do not overclaim certainty
- lead with the result
- keep the answer actionable

The goal of minimal mode is low overhead, not low discipline.

---

## Full-Repository Mode

If you are using this repository in an environment where the full repository is available at once, do **not** treat every module as active at the same time.

Instead, use:

- `CLAUDE.md`
- `AUTOLOAD.md`

as the global starting pair.

### Why

This repository is designed as a modular system.

That means:
- the full repository may be available
- but only a task-relevant subset should become active for the current task

Important distinction:

- **available modules** = all modules present in the repository
- **active modules** = only the modules selected for the current task

`AUTOLOAD.md` defines the policy for that selective activation.

### Recommended Full-Repository Startup

In a repository-wide environment, begin with:

- `CLAUDE.md`
- `AUTOLOAD.md`

Then allow the task to activate additional modules through:
- pack match
- primary behavior selection
- domain selection
- workflow selection
- template and checklist selection

### Preferred Activation Strategy

Use this order:

1. try a pack if the task strongly matches a repeated scenario
2. otherwise choose one primary behavior
3. activate only relevant domains
4. choose the smallest safe workflow
5. choose the simplest fitting template
6. apply proportional checklists
7. expand only if the task grows in risk, complexity, or uncertainty

### Example

User request:
"Review this Spring Boot caching service for stale-read risks."

Full-repository startup:
- `CLAUDE.md`
- `AUTOLOAD.md`

Likely activation result:
- `behavior.review`
- `domain.java`
- `domain.spring`
- `domain.redis`
- `domain.testing`
- `workflow.light_review`
- `template.review_report`
- relevant review/verification/delivery checklists

The important point is that the whole repository is visible, but only this subset becomes active.

### What to Avoid

Avoid:
- treating the entire repository as always-on active context
- activating all domains for every task
- forcing the full workflow on every small task
- using full-repo mode as an excuse to ignore task scoping

### When Full-Repository Mode Is Most Useful

This mode is especially useful when:
- the environment can access repository files dynamically
- the same assistant handles many task types
- packs are available for repeated scenarios
- you want modular consistency without manual file picking every time

### Relationship to Minimal Mode

Minimal mode and full-repository mode are compatible.

- Minimal mode means loading only the smallest useful subset manually.
- Full-repository mode means the full repository is available, but activation still remains selective.

The key principle is the same in both cases:

> use the smallest sufficient active module set for the task.

---

## Minimal Manual Usage

If you are using this repository manually, use this sequence.

### Step 1: Load the kernel

Always start with:

`CLAUDE.md`

This gives the global operating principles:

- evidence over speculation
- context before conclusions
- explicit uncertainty
- composability
- verification honesty

### Step 2: Identify the task type

Pick the main behavior:

| User says | Load |
|---|---|
| "Review this code" | `review.md` |
| "Why is this failing?" | `debug.md` |
| "Refactor this class" | `refactor.md` |
| "Optimize this" | `optimize.md` |
| "Write docs for..." | `document.md` |
| "Explain this" | `explain.md` |

### Step 3: Identify the domain(s)

Pick only the domains that materially affect the task.

| Technology | Load |
|---|---|
| Java + Spring service | `java.md`, `spring.md` |
| Redis cache logic | `redis.md` |
| Playwright test | `playwright.md`, `testing.md` |
| MySQL query | `mysql.md` |
| Spring AI workflow | `spring-ai.md`, `spring.md` |

### Step 4: Choose the engine path

Default full path:

```
discover -> evidence -> context -> reasoning -> planning -> execution -> verification -> delivery
```

Common simplifications:

| Task type | Engine path |
|---|---|
| explanation task | `discover -> context -> reasoning -> delivery` |
| lightweight review | `discover -> evidence -> reasoning -> delivery` |
| diagnosis only | `discover -> evidence -> context -> reasoning -> delivery` |
| full implementation | full default path |

### Step 5: Choose output shape

Pick a template:

| Task | Template |
|---|---|
| review | `review-report.md` |
| debug | `debug-report.md` |
| refactor | `refactor-plan.md` |
| implement | `implementation-plan.md` |
| explain | `explanation.md` |
| simple answer | `default.md` |

Then apply:

- `general-quality.md`
- task-specific checklist
- `delivery-checklist.md`
- `verification-checklist.md` when correctness matters

---

## Recommended First Task Flow

If you want one default starting pattern for most engineering tasks, use:

1. Load `CLAUDE.md` + `/runtime/router.md`
2. Then select:
   - 1 primary behavior
   - 1-3 relevant domains
   - 1 template
   - 2-4 checklists
3. Then run:
   ```
   discover -> evidence -> context -> reasoning -> planning -> execution -> verification -> delivery
   ```

This is a strong default for non-trivial tasks.

---

## Usage Patterns

### Pattern 1: Code review

| Layer | Selection |
|---|---|
| behavior | `review` |
| engine | `discover, evidence, context, reasoning, verification, delivery` |
| template | `review-report` |
| common domains | `java`, `spring`, `redis`, `mysql`, `testing`, `playwright` |

### Pattern 2: Bug diagnosis

| Layer | Selection |
|---|---|
| behavior | `debug` |
| engine | `discover, evidence, context, reasoning, delivery` |
| template | `debug-report` |
| optional | `planning` and `verification` if proposing a fix path |

### Pattern 3: Refactor planning

| Layer | Selection |
|---|---|
| behavior | `refactor` |
| engine | `discover, evidence, context, reasoning, planning, verification, delivery` |
| template | `refactor-plan` |

### Pattern 4: Feature/change plan

| Layer | Selection |
|---|---|
| template | `implementation-plan` |
| behavior | often `review`, `optimize`, or custom |
| engine | full path except sometimes minimal execution |

### Pattern 5: Concept explanation

| Layer | Selection |
|---|---|
| behavior | `explain` |
| engine | `discover, context, reasoning, delivery` |
| template | `explanation` |

---

## How to Use This in an Agent System

A practical agent runtime can do this:

**Phase 1: classify**
Detect:
- task type
- likely technologies
- expected deliverable

**Phase 2: assemble context**
Load:
- kernel
- composition
- selected behavior files
- selected domain files
- selected template
- selected checklists

**Phase 3: execute workflow**
Follow the selected engine stages.

**Phase 4: quality gate**
Run checklist validation before final answer.

**Phase 5: deliver or persist**
Return a conversational answer or emit a `/reports/*` artifact.

---

## Human-Friendly Composition Rule

If you are unsure what to load, use this rule:

| Frequency | Load |
|---|---|
| Always | `CLAUDE.md` |
| Usually | `/runtime/router.md`, the relevant behavior, the relevant domains, the relevant template, `general-quality.md` |
| Sometimes | extra engine files explicitly, reports, governance docs, advanced runtime docs |

This lets you start small.

---

## Example Starter Sets

> **Path convention**: Paths prefixed with `/` below are relative to the forge root (`.claude/forge/`). For example, `/behaviors/review.md` resolves to `.claude/forge/behaviors/review.md`. Skill references outside forge use the full `.claude/skills/` path.

### Starter set: Spring code review

Load:
- `CLAUDE.md`
- `/runtime/router.md`
- `/behaviors/review.md`
- `/domains/java.md`
- `/domains/spring.md`
- `/domains/testing.md`
- `/templates/review-report.md`
- `/checklists/general-quality.md`
- `/checklists/review-checklist.md`
- `/checklists/delivery-checklist.md`

### Starter set: Redis consistency investigation

Load:
- `CLAUDE.md`
- `/runtime/router.md`
- `/behaviors/debug.md`
- `/domains/java.md`
- `/domains/spring.md`
- `/domains/redis.md`
- `/domains/mysql.md`
- `/templates/debug-report.md`
- `/checklists/general-quality.md`
- `/checklists/debug-checklist.md`
- `/checklists/verification-checklist.md`

### Starter set: Playwright flaky test

Load:
- `CLAUDE.md`
- `/runtime/router.md`
- `/behaviors/debug.md`
- `/domains/playwright.md`
- `/domains/testing.md`
- `/templates/debug-report.md`
- `/checklists/general-quality.md`
- `/checklists/debug-checklist.md`
- `/checklists/delivery-checklist.md`

---

## Common Mistakes When Starting

Avoid:

- loading too many domains "just in case"
- using review behavior for every task
- skipping discover because the task looks obvious
- forcing a formal template on tiny tasks
- skipping verification while claiming correctness
- using domain files as if they define process

---

## If You Only Remember One Thing

Use this formula:

```
Principles + Workflow + Behavior + Domain + Template + Checklist
```

That is the whole system in one line.

---

## Next Reading

After this guide, read:

- `EXAMPLES.md`
- `ARCHITECTURE.md`
- `/runtime/runtime-contract.md`

---

## Local Checks

forge includes a suite of local validation and regression tools. Run these after modifying registry files, schemas, routing config, packs, or skills to verify the system remains consistent.

### What Gets Checked

1. **`validate`** — seven deterministic checks: registry JSON/schema validity, module paths, cross-references, pack schemas, pack references, semantic invariants, and declared contract fixtures
2. **`validate --report`** — the same seven checks plus an explicitly requested structured JSON report
3. **`doctor --report`** — health-oriented subset (registry + paths + refs) with an explicitly requested JSON report
4. **`check-route-regression.py`** — runs all route/recommend regression cases from `route-regression.json`, verifying skill routing, pack selection, confidence levels, and forbidden skill/pack constraints
5. **`check-documentation-facts.py`** — checks designated public inventory and validation facts against the registries and CLI constants

### Output Directory

Reports are opt-in diagnostics written to a path you choose with `--report`; the default local gate is non-mutating and does not maintain committed report snapshots.

### Running Checks

Use quick mode for commit-time feedback:

```bash
.claude/forge/scripts/run-local-checks.sh --quick
```

Use full mode before release or in CI. Omitting `--full` preserves the same full behavior.

**macOS / Linux / Git Bash:**
```bash
chmod +x .claude/forge/scripts/run-local-checks.sh
.claude/forge/scripts/run-local-checks.sh --full
```

**Windows CMD:**
```bat
.claude\forge\scripts\run-local-checks.bat --full
```

### Manual Step-by-Step

If you prefer to run each step individually:

```bash
# 1) Full validation from the Forge root
cd .claude/forge
python -m forge_cli --root . validate

# 2) Validation with an explicit diagnostic report
python -m forge_cli --root . validate --report out/validate-report.json

# 3) Health check with an explicit diagnostic report
python -m forge_cli --root . doctor --report out/doctor-report.json

# 4) Route regression
python scripts/check-route-regression.py

# 5) Documentation facts
python scripts/check-documentation-facts.py
```

### When to Run

Run local checks after changing:

- `registry/*.json` or `registry/schemas/*.json`
- `skills.json` or `skill-routing.json`
- `packs.json` or `packs/*.json`
- `forge_cli/` modules (route/recommend/compose/validate logic)
- `route-regression.json` (regression test data)

### Pass Criteria

- **validate**: all 8 checks pass, 0 errors
- **route regression**: 0 unexpected failures
- **documentation facts**: designated public facts match registries and CLI constants, including the current validation-check count
- **derived registry**: `modules.json` layer identities match their dedicated registries; use `python -m forge_cli --root . registry-sync --check` to inspect drift
- **pytest**: complete suite passes
- **reports**: generated only when explicitly requested for diagnostics

### Troubleshooting

| Symptom | Check |
|---------|-------|
| `validate` fails | Schema file exists? Registry JSON valid? Reference IDs spelled correctly? Paths exist on disk? |
| Route regression fails | `skill-routing.json` bias rules correct? Pack `routing.preferred_skill` valid? Historical regression re-triggered? |
| Reports not generated | `.claude/forge/out/` writable? Python executable working? `python -m forge_cli --root . doctor --report ...` succeeds? |

### Recommended Workflow

```bash
# After any forge config or routing change:
.claude/forge/scripts/run-local-checks.sh   # or .bat on Windows

# Confirm pass, then continue iterating.
```
