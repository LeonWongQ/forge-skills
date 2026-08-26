# Modular AI Engineering Assistant

## Current Version

`v1.2.1`

<!-- forge-facts: skills=31 packs=9 domains=12 checklists=10 templates=9 validation-count=8 validation-checks=registry,paths,refs,packs,pack-refs,semantics,contracts,derived-registry version=1.2.1 route-regression-count=81 -->

This release closes the Operational Validation, Compatibility, and Routing Calibration milestone.

At this version, the repository includes:

- stable architectural layering
- runtime orchestration guidance
- behavior and domain modularity
- templates and checklists
- reports
- machine-readable registries
- schemas
- validation scripts and an intentionally dormant CI template
- reusable task packs
- testing-specific planning and reporting templates

For repository-wide task-scoped activation in environments such as Claude Code, see `AUTOLOAD.md`.

---

## What this repository is

This repository is a modular operating model for an AI engineering assistant.

Instead of putting all rules, workflows, technical heuristics, and output formats into one giant prompt, this repository separates them into composable layers:

- `CLAUDE.md` defines global principles
- `/engine` defines workflow stages
- `/runtime` defines task routing and orchestration
- `/behaviors` defines task modes
- `/domains` defines technical expertise
- `/templates` defines output shape
- `/checklists` defines quality gates
- `/reports` defines reusable report artifacts
- `/STANDARDS` defines governance for evolution

The result is a system that is:
- easier to maintain
- easier to extend
- easier to audit
- easier to compose for different task types

---

## Why this exists

Large monolithic prompts usually degrade over time.

Common problems:
- workflow, domain knowledge, and formatting become tangled
- one change affects unrelated tasks
- review/debug/refactor modes are not truly distinct
- outputs become inconsistent
- adding new technologies or task types becomes messy

This repository solves that by separating concerns.

---

## Current Maturity

This repository is best understood as:

> an architecture-complete modular AI engineering operating model with growing operational tooling support

### What is mature
- architectural layering
- module boundaries
- workflow and runtime structure
- behavior and domain composition
- output template design
- quality-gate design
- machine-readable metadata design

### What is usable today
- human-guided modular usage
- AI agent integration
- task-pack based composition
- registry and deterministic semantic validation
- fixture-backed API/event contract compatibility validation
- template-bound structured JSON output validation
- deterministic semantic validation for registry and routing references
- local quality gate (validate, route regression, documentation facts, pytest) with calibrated routing diagnostics

### What is still intentionally lightweight
- runtime implementation code
- automatic registry generation
- CI activation for the junction-deployed source model
- consumer-project junction verification is performed automatically by `link-forge.bat` on Windows
- UI-based module/pack selection
- end-to-end LLM structured-output execution (validation of supplied JSON is available)

In short:

- the architecture is complete
- the repository is usable now
- future work is mostly operational and tooling-oriented rather than architectural

---

## Core model

### Kernel
Global principles and invariants.

File:
- `CLAUDE.md`

### Engine
Workflow stages.

Examples:
- discover
- evidence
- context
- reasoning
- planning
- execution
- verification
- delivery

### Runtime
Task routing and orchestration.

Examples:
- router
- runtime-contract
- conflict-resolution

### Behaviors
How the assistant should think while doing the task.

Examples:
- review
- debug
- refactor
- optimize
- document
- explain

### Domains
Technology-specific heuristics and failure modes.

Examples:
- java
- spring
- spring-ai
- mysql
- redis
- playwright
- testing
- vue2 / vue2-7 / vue3-vite

### Templates
How the result should be shaped.

Examples:
- review-report
- debug-report
- refactor-plan
- implementation-plan
- explanation
- default

### Checklists
How quality is checked before delivery.

### Reports
How results can be stored as reusable artifacts.

---

## Repository structure

```text
.claude/
├── CLAUDE.md          ← project-root user instructions
├── rules/             ← alwaysApply rule files (e.g., 000-forge.mdc)
├── forge/             ← modular engineering architecture
│   ├── CLAUDE.md      ← forge kernel (universal principles)
│   ├── README.md
│   ├── GETTING-STARTED.md
│   ├── EXAMPLES.md
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTING.md
│   │
│   ├── engine/        ← workflow stages
│   ├── runtime/       ← routing and execution contracts
│   ├── behaviors/     ← thinking modes (review, debug, refactor, optimize, document, explain)
│   ├── domains/       ← tech expertise (12 domains)
│   ├── templates/     ← output shapes (9 templates)
│   ├── checklists/    ← quality gates (10 checklists)
│   ├── reports/       ← persistent artifacts (3 report types)
│   ├── packs/         ← pre-composed task bundles (9 packs)
│   ├── INTEGRATIONS/  ← Cursor, OpenAI agents, etc.
│   ├── registry/      ← machine-readable metadata and schemas
│   └── scripts/       ← validation and local quality tooling
└── skills/            ← task-specific workflows (27 skills)
    ├── code-review/
    ├── debug/
    ├── plan/
    ├── error-analysis/
    ├── report/
    ├── explain/
    ├── refactor/
    ├── optimize/
    ├── document/
    ├── explore/
    ├── implement/
    ├── architecture-design/
    ├── security-review/
    ├── data-design/
    ├── dependency-audit/
    ├── test-design/
    ├── test-implementation/
    ├── test-strategy/
    ├── page-test/
    ├── incident/
    ├── migration/
    ├── release-readiness/
    ├── contract-compatibility/
    ├── auto-compact/
    ├── vite-vue3/
    ├── vue2/
    ├── vue2-7/
    └── forge/          ← forge CLI (validate, route, doctor)
```

---

## Basic usage model

A task is handled by composing modules.

Typical composition flow:

1. Load `CLAUDE.md`
2. Route the task using `/runtime/router.md`
3. Select one or more behaviors
4. Select relevant domains
5. Select an engine path
6. Select a template
7. Apply relevant checklists
8. Deliver the result
9. Optionally emit a report artifact

In full-repository environments, this composition may be guided automatically by `AUTOLOAD.md`.

In repeated high-value task types, composition may also begin from a predefined pack rather than from fully manual assembly.

Examples:
- Spring service review
- Playwright flaky test diagnosis
- Redis stale-read incident analysis
- Java refactor planning
- Vue 3 / Vite feature implementation

---

## Repository-wide Autoload

This repository may be fully present in the workspace without requiring every module to be active in every task.

To support that model, the repository includes:

- `AUTOLOAD.md`

`AUTOLOAD.md` defines the global policy for:

- task-scoped activation
- pack-first routing for strong repeated scenarios
- minimal-first loading for small tasks
- expansion-on-demand for deeper or riskier work

This means the repository can be used in a full-repo environment without collapsing back into one giant always-on prompt.

Important distinction:

- **available modules** = modules present in the repository
- **active modules** = modules selected for the current task

The repository is designed to keep those two concepts separate.

For practical use in repository-wide environments, start with:
- `CLAUDE.md`
- `AUTOLOAD.md`

Then allow task-relevant behaviors, domains, workflows, templates, checklists, or packs to become active only as needed.

---

## Example compositions

### Example: review Spring caching code

| Layer | Selection |
|---|---|
| Behavior | `review` |
| Domains | `java`, `spring`, `redis`, `testing` |
| Engine path | `discover -> evidence -> context -> reasoning -> verification -> delivery` |
| Template | `review-report` |
| Checklists | `general-quality`, `review-checklist`, `verification-checklist`, `delivery-checklist` |

### Example: debug flaky Playwright test

| Layer | Selection |
|---|---|
| Behavior | `debug` |
| Domains | `playwright`, `testing` |
| Engine path | `discover -> evidence -> context -> reasoning -> delivery` |
| Template | `debug-report` |
| Checklists | `general-quality`, `debug-checklist`, `delivery-checklist` |

### Example: refactor a Spring service

| Layer | Selection |
|---|---|
| Behavior | `refactor` |
| Domains | `java`, `spring`, `testing` |
| Engine path | `discover -> evidence -> context -> reasoning -> planning -> execution -> verification -> delivery` |
| Template | `refactor-plan` |
| Checklists | `general-quality`, `refactor-checklist`, `verification-checklist`, `delivery-checklist` |

---

## Who this is for

This repository is useful for:

- engineering assistants
- code review agents
- debugging agents
- refactoring assistants
- internal AI tooling
- prompt engineering systems
- teams building reusable AI workflows for software work

---

## How to start

Read in this order:

1. `README.md`
2. `GETTING-STARTED.md`
3. `ARCHITECTURE.md`
4. `CLAUDE.md`

Then explore:

- `/engine` to understand process
- `/behaviors` to understand task modes
- `/domains` to understand technical modules
- `/templates` and `/checklists` to understand output and quality control

If you are using this repository in a repository-wide environment such as Claude Code, also read:

- `AUTOLOAD.md`

This file explains how to keep the full repository available while activating only the task-relevant subset of modules.

---

## Local Checks

After modifying registry, schema, routing, packs, or skills, run local checks to verify system consistency.

### Commit-Time Quick Run

**macOS / Linux / Git Bash:**
```bash
chmod +x .claude/forge/scripts/run-local-checks.sh
.claude/forge/scripts/run-local-checks.sh --quick
```

**Windows CMD:**
```bat
.claude\forge\scripts\run-local-checks.bat --quick
```

### Full Run

Run `.claude/forge/scripts/run-local-checks.sh --full` or
`.claude\forge\scripts\run-local-checks.bat --full` before release and in CI.
Omitting the mode flag remains equivalent to `--full`.

### What it checks

| Step | Command | Validates |
|------|---------|-----------|
| Step | Quick | Full | Validates |
|------|:-----:|:----:|-----------|
| Skill quality | Yes | Yes | Skill frontmatter, UI metadata, size limits, and local references |
| Skill behavior corpus | Yes | Yes | Versioned forward-test prompts, categories, skills, and rubric structure |
| `validate` | Yes | Yes | Registry JSON, schemas, paths, refs, packs, semantics, contracts, and derived identities |
| Route regression | No | Yes | Route/recommend behavior against `route-regression.json` |
| Documentation facts | No | Yes | Published version, inventory, validation, and regression-corpus facts |
| `pytest` | No | Yes | CLI, registry, routing, output contracts, validators, and runtime behavior |

The default local gate is non-mutating: it does not generate reports. Use `validate --report` or `doctor --report` explicitly when diagnostic artifacts are needed.

The skill behavior corpus is an evaluation input, not a claim that model behavior passed.
Run its prompts against the candidate agent and score the hard requirements and forbidden
behaviors before using it as a release signal.

### Consumer deployment

Forge keeps `.claude/` as the source-checkout layout. Consumer projects use the selected host directory: `.claude/` for Claude Code, `.cursor/` for Cursor, and `.codex/` for Codex. Runtime manifests and Context Bundles derive their prefix from the active Forge installation, so a Codex deployment resolves and reports `.codex/...` paths.

For a standalone Forge root outside these host directories, manifests use relative paths such as `./CLAUDE.md` and `../skills/example/SKILL.md`; they do not fall back to a misleading `.claude/...` prefix.

`install-link-forge.bat` first confirms Python 3.11+ before it creates project paths or junctions, then verifies the Windows junction targets before reporting installation success. It runs directly from the source checkout, so it does not require `pip install`, Forge development dependencies, a global `forge` command, or manual PATH changes.

`validate` and `run-local-checks` separately verify the linked Forge source internals.

---

### Resolve a read-only context manifest

```bash
# Route natural language, then resolve the selected modules and safe paths
python -m forge_cli --root . --format json resolve "帮我 review 一个 spring service 改动"

# Resolve an explicit composition without routing
python -m forge_cli --root . --format json resolve --skill code-review --domain domain.spring

# Check five modules.json layer projections; --write is an explicit maintenance action
python -m forge_cli --root . registry-sync --check
```

The `resolve` command does not load module content or execute a model. It emits a versioned selection and path manifest for inspection or downstream tooling.

### Initialize a thin runtime envelope

The additive runtime commands create and validate a portable, provider-neutral task envelope. They do **not** invoke a model, manage credentials, scan a repository, or change deployment behavior.

```bash
# Build a runtime state, evidence-aware domain selection, and append-only ledger.
python -m forge_cli --root . --format json runtime-init \
  "帮我 review 一个 spring service 改动" --output runtime.json

# Prepare a standard adapter request for an external host; no provider call occurs.
python -m forge_cli --root . --format json runtime-prepare \
  --runtime runtime.json --output prepared-runtime.json

# Import one normalized external result, then explicitly select the handoff.
# `next` is allowed only for a successful stage result; `retry`/`abort` are
# available for failed or blocked results. Forge never executes the host work.
python -m forge_cli --root . --format json runtime-import-result \
  --runtime prepared-runtime.json --result adapter-result.json --output imported-runtime.json
python -m forge_cli --root . --format json runtime-advance \
  --runtime imported-runtime.json --action next --output advanced-runtime.json

# Repeat runtime-prepare → external host → import → advance for each selected
# workflow stage. The final `next` produces ready_for_validation.
python -m forge_cli --root . --format json validate-runtime-output \
  --runtime final-runtime.json --input final-linked-output.json
```

Runtime state is caller-owned: Forge writes JSON only when an explicit `--output` path is supplied. The runtime records checklist selection but does not claim that Markdown checklists are machine-executable policies.

### Materialize a Context Bundle for an external host

A Context Bundle is an explicit, provider-neutral snapshot of the Markdown instructions selected by a Runtime Envelope. It captures complete strict UTF-8 module content, canonical layer order, source paths, byte counts, per-module digests, and a bundle digest. Hosts should consume the captured content rather than rereading source paths.

```bash
python -m forge_cli --root . --format json context-bundle \
  --runtime runtime.json --output context-bundle.json
```

By default, each module is limited to 256 KiB and the aggregate bundle to 2 MiB. Use `--max-module-bytes` and `--max-bundle-bytes` only when a caller has explicitly accepted a larger context. Forge fails closed on unsafe paths, invalid UTF-8, binary-like content, or size overflow; it never silently truncates selected instructions. The command does not invoke a model, scan arbitrary repository files, or modify deployment/Junction behavior.

To bound prompt size, pass `--max-estimated-tokens N`. Forge keeps modules in canonical order until the budget is reached, records every skipped module in the bundle, and includes the applied estimate in the digest. The estimate is provider-neutral rather than a model-specific tokenizer count: ASCII text is estimated at four characters per token and non-ASCII characters at one token each. Keep a margin for host-generated prompts and use a host tokenizer when an exact provider limit is required.

### Prepare a Claude Code host handoff

For caller-managed Claude Code sessions, transform a prepared Runtime Envelope plus matching Context Bundle into an auditable host request. The artifact has ordered stable module instructions, dynamic task/stage state, digest linkage, and a prefilled result skeleton. It does not call Claude Code or grant any tool permissions.

```bash
python -m forge_cli --root . --format json claude-code-prepare \
  --runtime prepared-runtime.json --bundle context-bundle.json \
  --output claude-code-request.json

# The host fills the result skeleton after its own Claude Code session completes.
python -m forge_cli --root . --format json claude-code-validate-result \
  --request claude-code-request.json --result claude-code-result.json \
  --output normalized-adapter-result.json

python -m forge_cli --root . --format json runtime-import-result \
  --runtime prepared-runtime.json --result normalized-adapter-result.json \
  --output completed-runtime.json
```

The host request is an SDK-free portable artifact, not a prescribed Claude Code CLI or Agent SDK invocation. The caller owns the session, workspace, tool permissions, tool execution, streaming, retries, approvals, and normalized result content. Forge validates request/result linkage and only advances after an explicit `runtime-advance` action; it never evaluates host work or controls the session. Repeat the prepare → host → validate-result → import → advance loop for every selected workflow stage, then use `validate-runtime-output` only after the final successful stage reaches `ready_for_validation`.

---

### Validate API/event contract fixtures

Run this from the Forge root, or use the installed `forge` command after `python -m pip install -e ".[dev]"`:

```bash
python -m forge_cli --root . validate --check contracts
```

Contract entries live in `registry/contracts.json`; schemas and fixtures are explicitly registered. This proves only declared JSON fixture acceptance. It does not infer generic schema compatibility or prove runtime delivery, ordering, idempotency, external-consumer, or rollout behavior.

### Validate structured output

Validate an already-produced JSON document against the schema bound to a canonical template ID:

```bash
python -m forge_cli --root .claude/forge --format json validate-output \
  --template template.default --input path/to/output.json
```

This command validates supplied JSON only; it does not invoke a model or parse prose into JSON.

### Manual equivalent

```bash
python -m forge_cli --root .claude/forge validate
python .claude/forge/scripts/check-route-regression.py
python -m pytest .claude/forge/tests
```

---

## What to Expect Next

Future evolution of this repository is expected to focus on:

- tooling
- automation
- validation depth
- runtime implementation
- pack-driven operational workflows

In other words, future work should mostly build **on top of** the architecture rather than repeatedly redesigning it.

Examples of likely next-step improvements:
- registry generation from module metadata
- stronger cross-reference validation
- pack loaders or simple CLI tools
- output validation against template schemas
- richer runtime execution tooling

This should be seen as a sign of maturity:
the repository has moved from "still defining the architecture" to "ready for operational expansion."

---

## Contribution philosophy

This repository should evolve by:

- refining modules
- adding clearly reusable modules
- preserving separation of concerns
- resisting bloat

See:

- `CONTRIBUTING.md`
- `ARCHITECTURE.md`
- `/STANDARDS/*`

---

## Short summary

This repo is an AI engineering operating system made of composable markdown modules.

If a monolithic prompt is a script, this repository is a modular runtime.
