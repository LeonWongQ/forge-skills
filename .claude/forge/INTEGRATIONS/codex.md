# Integration: Code X

## Automated Setup

Deploy Forge into a Code X project from the Forge source repository:

```bat
install-link-forge.bat <target_project_path> --tool codex
```

The link tool creates directory junctions under the target project:

```text
.codex/forge
.codex/skills
.codex/rules    # when the Forge source rules directory exists
```

The installer requires Python 3.11+ before it creates any project paths, then verifies deployment topology automatically before reporting success. It uses the source checkout without installing Forge/development dependencies or requiring a global `forge` command or manual PATH update.

## Runtime Layout

- `.codex/forge/` contains the Forge kernel, registry, runtime, domains, templates, and checklists.
- `.codex/skills/` contains the task-entry `SKILL.md` definitions.
- `.codex/rules/` contains shared Forge rules when linked by the source layout.

Use task-relevant modules selectively. The deployment makes modules available; it does not make all modules active for every task.
