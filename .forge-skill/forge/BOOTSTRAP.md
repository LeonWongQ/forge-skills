# Consumer Project Bootstrap

Use this guide to link Forge into another project and add task-scoped discovery
instructions. Source files live in `.forge-skill/`; installed paths use the
chosen host directory.

## Install

From the source repository root on Windows:

```bat
install-link-forge.bat "<target-project-path>" --tool claude
```

The `--tool` option accepts `claude|cursor|codex`. The installer requires Python 3.11+,
preserves conflicting real directories by reporting a conflict, and
verifies the resulting junction targets before reporting success. It does not require a global
`forge` command or development dependencies.

| Host | Project installation paths |
|---|---|
| Claude Code | `.claude/forge`, `.claude/skills`, `.claude/forge-data` |
| Codex | `.codex/forge`, `.codex/skills`, `.codex/forge-data` |
| Cursor | `.cursor/forge`, `.cursor/skills`, `.cursor/forge-data` |

For Codex and Cursor, `rules` is linked only when the optional source directory
exists. Linking rules does not by itself establish that a host loads them.

The cross-platform Skill installer is another installation option:

```bash
python .forge-skill/forge/scripts/sync-agent-skills.py --client claude --scope project --project "<target-project-path>" --check
python .forge-skill/forge/scripts/sync-agent-skills.py --client claude --scope project --project "<target-project-path>"
```

See the [root README](../../README.md) for global installation and uninstall options.

## Add Host Instructions

For Claude Code, add the following to the target project's `CLAUDE.md`.
Preserve the project's existing instructions.

```markdown
## Forge Engineering System

Forge is installed under .claude/ in this project.

1. Read .claude/forge/CLAUDE.md for shared principles.
2. Read .claude/forge/AUTOLOAD.md for task-scoped activation and host ownership.
3. Preserve explicit host Skill calls and native specialist ownership, then
   apply .claude/forge/registry/skill-routing.json ask_policy.
4. Use matching .claude/skills/ entrypoints and relevant .claude/forge/packs/.
5. If no entrypoint applies, consult .claude/forge/runtime/router.md.

Load only task-relevant modules. Prefer project code, configuration, and runtime
evidence over generic examples. Expand the workflow only when scope or risk
requires it.
```

For Codex, place the adapted instructions in the project's `AGENTS.md` and
replace every `.claude/` path with `.codex/`.
For Cursor, adapt the paths to `.cursor/` and use the project's host-loaded
instruction entrypoint; see [Cursor integration](INTEGRATIONS/cursor.md).
Never copy source-only `.forge-skill/forge` paths into a project that has only
host-directory links.

## Source Layout

```text
<source-repository>/.forge-skill/
├── forge/
├── skills/
├── rules/
└── forge-data/
```

For manual Windows linking, run these commands from the target project root,
using the real source checkout path:

```bat
mklink /J .claude\forge "<forge-source-root>\.forge-skill\forge"
mklink /J .claude\skills "<forge-source-root>\.forge-skill\skills"
mklink /J .claude\forge-data "<forge-source-root>\.forge-skill\forge-data"
```

Create the `.claude` parent directory first if needed. Prefer the installer,
which verifies targets and handles conflicts.

## Runtime and Learning Hooks

Forge does not install a Claude Code `SessionStart` Hook to automatically resume
Runtime work. An explicitly persisted Runtime is discovered and handed off only
when the user requests it. Existing unrelated Runtime data is preserved.

Learning collection is a separate opt-in workflow. Linking Forge does not prove
that a native collection Hook is enabled, trusted, or successfully capturing.
See [Hook doctor](../skills/hook-doctor/SKILL.md) and the
[learning lifecycle](../skills/learning-collector/references/lifecycle.md).

## Further Reading

- [Quick start](QUICKSTART.md)
- [Module integration](GETTING-STARTED.md)
- [Codex integration](INTEGRATIONS/codex.md)
- [Claude Code integration](INTEGRATIONS/claude-code.md)
