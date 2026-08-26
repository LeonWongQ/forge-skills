---
name: forge
description: >-
  Run Forge validation and runtime tools: validate registry, paths,
  cross-references, and pack integrity; inspect status, version, doctor, list,
  and show output; or manage paused runtime tasks. Use for forge/ff validate,
  check, status, version, doctor, list, show, runtime suspend/resume, 校验 Forge,
  检查 Forge, or 查看/继续 Forge Runtime 任务.
---

# Forge CLI

<!-- forge-facts: validation-count=8 validation-checks=registry,paths,refs,packs,pack-refs,semantics,contracts,derived-registry -->

The forge CLI validates registry integrity, path consistency, cross-references, and pack structure for the modular AI engineering operating system.

## Recommended Invocation

### Source checkout only

The following commands are for maintaining the shared Forge source checkout only. Never use them while operating a consumer project:

```bash
cd .claude/forge
python -m pip install -e ".[dev]"
forge version
```

Use `python -m forge_cli` from `.claude/forge` while developing the source. `python .claude/skills/forge/forge.py` remains a backward-compatible shim that delegates to the package CLI.

### Linked consumer projects (no package installation required)

From a consumer project linked by `install-link-forge.bat`, use the compatibility shim rather than a bare `forge` executable or `python -m forge_cli`:

**Invocation invariant:** locate the existing tool directory in the current project, then call only that project's relative shim and Forge root. Do not call, report, or derive an installation target path, even when the project link is a Junction.

```powershell
$forgeToolDirectory = @('.codex', '.claude', '.cursor') |
  Where-Object { Test-Path (Join-Path $_ 'forge') } |
  Select-Object -First 1
if (-not $forgeToolDirectory) { throw 'Forge is not linked in the current project.' }
python "$forgeToolDirectory\skills\forge\forge.py" --root "$forgeToolDirectory\forge" ask "your request"
```

When reporting the command used, report the literal project-relative path passed to Python. Do not resolve the Junction target.

Use the active tool directory. For Codex, invoke the linked project shim:

```bash
python ".codex/skills/forge/forge.py" --root ".codex/forge" ask "your request"
```

For Claude Code and Cursor, replace `.codex` with `.claude` or `.cursor` respectively. Do not invoke the shared source checkout directly.

The shim adds the linked active tool directory (for example `.codex/forge`) to Python's import path, so it works even when the selected Python interpreter has not globally installed `forge_cli`.

### Global Codex fallback

When a project has no local `.codex/forge`, `.claude/forge`, or `.cursor/forge`, Forge automatically falls back to the logical global Codex installation at `$HOME/.codex/forge` when it is valid. The order is: explicit `--root`, `FORGE_ROOT`, project installation, then global Codex installation.

Run the global shim from the consumer project's working directory. The Forge definition is global, but all Forge Runtime state remains project-local under `.forge-runtime`:

The Runtime directory is independent of `.claude`, `.codex`, and `.cursor`. Never store project task state inside a client configuration directory. If a deployment uses a global Runtime store, it must partition state by a stable project identifier such as `global-runtime/<project-id>/`; one shared directory must never contain multiple projects' tasks.

```powershell
python "$HOME\.codex\skills\forge\forge.py" --root "$HOME\.codex\forge" ask "your request"
```

Do not resolve a global Junction when reporting commands or paths. Project-owned results, including Runtime paths, are reported relative to the current project, for example `.forge-runtime/my-task.json`.

### Runtime suspend from natural language

Use Claude Code's native background agent for ordinary requests to pause, continue later, or work in the background. A `Backgrounded agent` or Claude Code Task List entry is **not** a Forge Runtime and does not create `.forge-runtime/*.json`.

When the user asks conversationally to suspend a Forge Runtime task, first ask whether they want to persist the task. Do **not** write a Markdown todo, a Claude memory file, `MEMORY.md`, or any other substitute record. Persist only after an affirmative user response. An explicit `runtime-suspend --task` request remains an immediate persistence request.

```bash
python ".codex/skills/forge/forge.py" --root ".codex/forge" runtime-suspend --task "<task>"
```

Create a cross-session, project-local Forge Runtime only when the user explicitly asks for one, for example:

```text
Use Forge Runtime to suspend "<task>".
```

Forge writes a `ready` Runtime to the current project’s `.forge-runtime/<safe-task-name>.json` and reports its path, ID, status, and current stage. It does not prepare, execute, import, advance, archive, or delete work; it does not modify `.gitignore`. If the generated Runtime path already exists, it must not overwrite it. Report success only after this command returns successfully with `Forge Runtime: SAVED` or JSON `mode: runtime-suspended`.

When the user types `runtime-list-paused` or asks to view or continue Forge Runtime work in the current project, invoke this exact read-only command rather than answering from memories or the Claude Code Task List:

```bash
python ".codex/skills/forge/forge.py" --root ".codex/forge" runtime-list-paused --directory ".forge-runtime"
```

Present the candidates, obtain an explicit selection, then consume only that selected candidate. Consuming is a one-time handoff: it removes the selected persisted Runtime after returning its Envelope, so it cannot trigger duplicate continuation. Do not use these commands to list or resume Claude Code background agents.

## Quick Reference

```bash
forge version                                  # show version
forge status                                   # health summary
forge validate                                 # run all 8 checks
forge validate --quick                         # path check only
forge validate --check semantics
forge validate --check contracts
forge validate --strict
forge --format json validate
forge list skills                              # list by kind
forge show skill code-review
forge doctor                                   # quick health check
```

## Commands

### `version`
Show forge version from registry metadata.

### `status`
Show health summary: module counts per layer, registry/schema file counts, quick path check result.

### `validate`
Run validation checks. By default runs all 8: registry, paths, refs, packs, pack-refs, semantics, contracts, and derived-registry.

| Option | Effect |
|--------|--------|
| `--quick`, `-q` | Run only path check |
| `--check`, `-c` NAME | Run a specific check (repeatable) |
| `--strict`, `-s` | Warnings also cause failure |
| `--format json` | Machine-readable JSON output |

### `list <kind>`
List registry items by kind: `modules`, `skills`, `packs`, `workflows`, `compositions`, or any layer name (`kernel`, `engine`, `behaviors`, `domains`, `templates`, `checklists`, `reports`).

### `show <type> <query>`
Show details of one registry item. `<type>` is one of: `skill`, `pack`, `workflow`, `composition`, `module`, `behavior`, `domain`, `template`, `checklist`, `report`. `<query>` can be an id (`skill.code_review`) or display name (`code-review`).

### `doctor`
Fast health check: runs registry + paths + refs only.

## Global Options

| Option | Effect |
|--------|--------|
| `--root PATH` | Override forge root directory |
| `--verbose`, `-v` | Enable debug output |
| `--format text|json` | Output format |

## Available Checks

| Check | What it does |
|-------|--------------|
| `registry` | JSON syntax + JSON Schema compliance for all registry files |
| `paths` | Verify all registered module paths exist on disk |
| `refs` | Cross-reference validation (skills, compositions, workflows) |
| `packs` | Validate pack JSON files against packs.schema.json |
| `pack-refs` | Verify pack references point to known registry IDs |
| `semantics` | Validate deterministic cross-registry and composition invariants |
| `contracts` | Validate declared API/event JSON Schema fixtures in required directions |
| `derived-registry` | Verify synchronized identities across dedicated and aggregate registries |

## Dependencies

- Python 3.11+
- click (`pip install click`)
- jsonschema (`pip install jsonschema`) — optional, enables schema validation
