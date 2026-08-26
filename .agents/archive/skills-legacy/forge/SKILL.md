---
name: forge
description: Run forge validation tools — validate registry, check paths, cross-references, and pack integrity.
triggers:
  - forge validate
  - forge check
  - validate forge
  - check forge registry
  - 校验 forge
  - 检查 forge
  - forge 验证
  - forge
  - forge status
  - forge version
  - forge doctor
  - forge list
  - forge show
  - runtime-suspend
  - runtime-supend
  - runtime-list-paused
  - runtime-consume-paused
  - 查看暂停的任务
  - 查看 Forge Runtime 任务
  - 继续 Forge Runtime 任务
  - ff validate
  - ff check
  - ff status
  - ff version
  - ff doctor
  - ff list
  - ff show
  - ff
---

# Forge CLI

The forge CLI validates registry integrity, path consistency, cross-references, and pack structure for the modular AI engineering operating system.

## Recommended Invocation

Install from the linked Forge root for normal usage:

```bash
cd .Codex/forge
python -m pip install -e ".[dev]"
forge version
```

Use `python -m forge_cli` from `.Codex/forge` while developing the source. `python .Codex/skills/forge/forge.py` remains a backward-compatible shim that delegates to the package CLI.

### Linked consumer projects (no package installation required)

From a consumer project linked by `install-link-forge.bat`, use the compatibility shim rather than a bare `forge` executable or `python -m forge_cli`:

```bash
python ".Codex/skills/forge/forge.py" --root ".Codex/forge" ask "your request"
```

The shim adds the linked `.Codex/forge` directory to Python's import path, so it works even when the selected Python interpreter has not globally installed `forge_cli`.

### Runtime suspend from natural language

Use Codex's native background agent for ordinary “挂起”, “后台做”, or “稍后继续” work. A `Backgrounded agent` or Codex Task List entry is **not** a Forge Runtime and does not create `.forge/runtime/*.json`.

When the user says they want to use `runtime-suspend --task` (including the common typo `runtime-supend --task`) to persist a task, run the exact linked-project shim command. Do **not** write a Markdown todo, a Codex memory file, `MEMORY.md`, or any other substitute record:

```bash
python ".Codex/skills/forge/forge.py" --root ".Codex/forge" runtime-suspend --task "<task>"
```

Create a cross-session, project-local Forge Runtime only when the user explicitly asks for one, for example:

```text
用 Forge Runtime 挂起“<task>”这个任务
```

Forge writes a `ready` Runtime to the current project’s `.forge/runtime/<safe-task-name>.json` and reports its path, ID, status, and current stage. It does not prepare, execute, import, advance, archive, or delete work; it does not modify `.gitignore`. If the generated Runtime path already exists, it must not overwrite it. Report success only after this command returns successfully with `Forge Runtime: SAVED` or JSON `mode: runtime-suspended`.

When the user types `runtime-list-paused`, `查看暂停的任务有哪些`, or asks to view/continue Forge Runtime work in the current project, invoke this exact read-only command rather than answering from memories or the Codex Task List:

```bash
python ".Codex/skills/forge/forge.py" --root ".Codex/forge" runtime-list-paused --directory ".forge/runtime"
```

Present the candidates, obtain an explicit selection, then consume only that selected candidate. Consuming is a one-time handoff: it removes the selected persisted Runtime after returning its Envelope, so it cannot trigger duplicate continuation. Do not use these commands to list or resume Codex background agents.

## Quick Reference

```bash
forge version                                  # show version
forge status                                   # health summary
forge validate                                 # run all 7 checks
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
Run validation checks. By default runs all 7: registry, paths, refs, packs, pack-refs, semantics, and contracts.

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

## Dependencies

- Python 3.11+
- click (`pip install click`)
- jsonschema (`pip install jsonschema`) — optional, enables schema validation
