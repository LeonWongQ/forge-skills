# Forge Engineering Toolkit

<!-- forge-facts: skills=33 packs=9 domains=12 checklists=10 templates=9 validation-count=8 validation-checks=registry,paths,refs,packs,pack-refs,semantics,contracts,derived-registry version=1.2.1 route-regression-count=81 -->

Forge combines 33 engineering Skills with shared workflows, domain guidance,
routing, validation, and project learning. It supports Codex, Claude Code, and
Cursor. See the [repository README](../../README.md) for installation.

## Source Layout

```text
.forge-skill/
├── forge/       # Shared modules, CLI, registries, tests, and documentation
├── skills/      # Host-discoverable Skill entrypoints
├── rules/       # Shared host rules
├── learning/    # Local project learning configuration
└── forge-data/  # Local runtime data; excluded from tracked source
```

Project installations link `forge`, `skills`, and `forge-data` under the
selected host directory: `.codex/`, `.claude/`, or `.cursor/`.
Global installations place these companions beside the host's Skills directory.
The source checkout remains under `.forge-skill/`.

## Module Model

| Layer | Responsibility |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Shared principles and invariants |
| [AUTOLOAD.md](AUTOLOAD.md) | Task-scoped activation and host ownership |
| [engine](engine/) | Workflow stages |
| [runtime](runtime/) | Routing and execution contracts |
| [behaviors](behaviors/) | Review, debug, refactor, optimize, document, and explain modes |
| [domains](domains/) | Technology-specific guidance |
| [templates](templates/) and [checklists](checklists/) | Output structure and delivery checks |
| [packs](packs/) | Precomposed task-specific modules |
| [registry](registry/) | Machine-readable identities, paths, and contracts |

Modules are available to the host but loaded only when relevant to a task.
Skills supply task entrypoints; packs add guidance for specific technologies.

## CLI Development

From the repository root:

```bash
python -m pip install -e ".forge-skill/forge[dev]"
forge version
forge ask "review a spring service change"
forge --format json route "review a spring service change"
```

Python 3.11+ is required. Skill installation does not require installing the CLI
or development dependencies.

For ordinary engineering requests, `ask` applies host ownership policy and
returns a Forge or native handoff. Explicit learning-service and Runtime
requests use dedicated handlers. `route` and `recommend` expose routing
results without those `ask` handlers. A routing decision does not execute the
engineering task in the host.

The CLI also supports composition manifests, Context Bundles, Runtime envelopes,
host handoff artifacts, output validation, and fixture-based contract checks.
See the [scripts reference](scripts/README.md) for commands and boundaries.
Real model evaluation is opt-in; deterministic checks do not establish model quality.

## Project Learning

The opt-in learning workflow collects Skill results, reviews evidence, generates
batched AI Summaries, and builds project-specific Overlays from reviewed Summaries.
Evaluation, publication, and manual activation are separate stages.
Global Skill instructions remain unchanged.

See the [learning lifecycle](../skills/learning-collector/references/lifecycle.md)
and [Hook doctor](../skills/hook-doctor/SKILL.md) for configuration and diagnostics.

## Validation

From the repository root:

```bash
python .forge-skill/forge/scripts/run-local-checks.py --quick
python .forge-skill/forge/scripts/run-local-checks.py --full
```

The full gate includes text and sensitive-content checks, Skill quality,
behavior-corpus structure, registry validation, routing regression,
documentation facts, and tests. Reports require an explicit reporting command.

[GitHub Actions](../../.github/workflows/quality-gate.yml) runs the deterministic
gate on Windows, Ubuntu, and macOS, with Python compatibility checks.
These workflow definitions do not imply that a particular commit has passed CI.

## Further Reading

- [Quick start](QUICKSTART.md): install Skills or set up the CLI.
- [User guide](docs/forge-user-guide.md) / [中文使用说明](docs/forge-user-guide.zh-CN.md): CLI usage.
- [Module integration](GETTING-STARTED.md): compose instructions for an external host.
- [中文体系说明](GUIDE.zh-CN.md): layers, current capabilities, and boundaries.
- [Project bootstrap](BOOTSTRAP.md): consumer-project paths and entrypoint instructions.
- [Architecture](ARCHITECTURE.md) and [contributing](CONTRIBUTING.md): internal design and development.
