# Forge Skills

<!-- forge-facts: skills=31 version=1.2.1 route-regression-count=81 skill-eval-case-count=37 skill-eval-skill-count=31 -->

Forge Skills is a modular engineering Skill collection for Codex, Claude, and Cursor. It combines focused Skill entrypoints with deterministic routing, reusable engineering guidance, validation tooling, and opt-in LLM behavior evaluation.

## Requirements

- Python 3.11 or later for Forge validation and installation tooling; CI verifies 3.11, 3.12, and 3.13.
- Node.js 22 or later for the standalone `page-test` runtime; CI verifies Node.js 22.
- An existing Chrome, Edge, or Chromium installation for standalone browser work. The project never installs a browser automatically.

## Install Skills

The installer creates only missing links and preserves existing files, directories, and conflicting links.

Add `--uninstall` to remove only links created from this source checkout. Existing files and links to other sources are preserved. Use `--check --uninstall` to preview removals.

Windows:

```powershell
install-skills.bat --client codex --scope global
install-skills.bat --client claude --scope global
install-skills.bat --client cursor --scope global
```

macOS or Linux:

```bash
python .claude/forge/scripts/sync-agent-skills.py --client codex --scope global
python .claude/forge/scripts/sync-agent-skills.py --client claude --scope global
python .claude/forge/scripts/sync-agent-skills.py --client cursor --scope global
```

For one existing project, add `--scope project --project <path>`. Use `--check` first for a read-only installation report.

Default roots are `~/.codex/skills`, `~/.claude/skills`, and `~/.cursor/skills`. Windows uses directory junctions; POSIX systems use directory symlinks.

## Validate

Install deterministic development dependencies from `.claude/forge`, then run:

```bash
python .claude/forge/scripts/run-local-checks.py --full
```

The full gate validates UTF-8 text, sensitive-content rules, Skill quality, behavior-corpus structure, registries, paths, references, packs, contracts, routes, documentation facts, and tests. CI runs it on Windows, Ubuntu, and macOS.

## LLM Evaluation

Real model evaluation is opt-in and user assessed. The runner never chooses a backend automatically, and a completed model response remains unscored until a human or calibrated judge applies the versioned rubric. Cursor supports prepared manual evaluation; automated Cursor execution remains disabled until a stable CLI contract is available.

See [.claude/forge/README.md](.claude/forge/README.md), [.claude/forge/BOOTSTRAP.md](.claude/forge/BOOTSTRAP.md), and [.claude/forge/scripts/README.md](.claude/forge/scripts/README.md) for architecture, project linking, and advanced commands.

## Publication Note

This project is distributed under the MIT License; see [LICENSE](LICENSE).
