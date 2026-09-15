# Forge Skills

<!-- forge-facts: skills=32 version=1.2.1 route-regression-count=81 skill-eval-case-count=40 skill-eval-skill-count=32 -->

Forge Skills is a modular engineering Skill collection for Codex, Claude, and Cursor. It combines focused Skill entrypoints with deterministic routing, reusable engineering guidance, validation tooling, and opt-in LLM behavior evaluation.

## Requirements

- Python 3.11 or later for Forge validation and installation tooling; CI verifies 3.11, 3.12, and 3.13.
- Node.js 22 or later for the standalone `page-test` runtime; CI verifies Node.js 22.
- An existing Chrome, Edge, or Chromium installation for standalone browser work. The project never installs a browser automatically.

## Install Skills

The installer creates only missing links and preserves existing files, directories, and conflicting links. Every global or project installation links the shared `forge` and `forge-data` companions beside the target `skills` directory.

Forge-generated runtime data is stored separately under `forge-data`, partitioned
by project ID and Skill. Project repositories retain only lightweight identity
and learning configuration files; databases, summaries, service state, and
paused Runtime documents are excluded from Git.

## Optional Skill Training Data

Forge includes an opt-in collector for improving Skill instructions and output
quality. Collection is disabled by default and is controlled per project in
`.forge-skill/learning/config.json`:

```json
{
  "schemaVersion": "1.0",
  "enabledSkills": ["code-review"],
  "collectorSkill": "learning-collector",
  "storage": "PROJECT_SQLITE"
}
```

Only the final, user-visible result of an explicitly enabled Skill is recorded.
Empty results, hidden reasoning, prompts, credentials, and intermediate Runtime
stages are excluded. Each project and Skill has an isolated SQLite database at
`forge-data/projects/<projectId>/learning/<skill>/learning.sqlite`.

Start the local review dashboard when needed:

```text
forge ask "启动学习审核页面"
forge ask "关闭学习审核服务"
```

The dashboard supports filtering, editing, exclusion, deletion, Summary
generation, LLM refinement, and manual version review. Reviewed Summary versions
can produce a project Overlay, but evaluation, publication, and activation remain
separate operator actions. At most one Overlay can be active for a project and
Skill. Machine-local collector settings live in `forge-data/runtime.json`, while
project learning configuration remains under `.forge-skill/learning/`. See the
[RC1 test guide](.forge-skill/forge/docs/SKILL-TRAINING-RC1.md) for the complete
test workflow and current limitations.

Add `--uninstall` to remove only links created from this source checkout. Existing files and links to other sources are preserved. Use `--check --uninstall` to preview removals.

Windows:

```powershell
install-skills.bat --client codex --scope global
install-skills.bat --client claude --scope global
install-skills.bat --client cursor --scope global
```

macOS or Linux:

```bash
python .forge-skill/forge/scripts/sync-agent-skills.py --client codex --scope global
python .forge-skill/forge/scripts/sync-agent-skills.py --client claude --scope global
python .forge-skill/forge/scripts/sync-agent-skills.py --client cursor --scope global
```

For one existing project, add `--scope project --project <path>`. Use `--check` first for a read-only installation report.

Default roots are `~/.codex/skills`, `~/.claude/skills`, and `~/.cursor/skills`. Windows uses directory junctions; POSIX systems use directory symlinks.

## Validate

Install deterministic development dependencies from `.forge-skill/forge`, then run:

```bash
python .forge-skill/forge/scripts/run-local-checks.py --full
```

The full gate validates UTF-8 text, sensitive-content rules, Skill quality, behavior-corpus structure, registries, paths, references, packs, contracts, routes, documentation facts, and tests. CI runs it on Windows, Ubuntu, and macOS.

## LLM Evaluation

Real model evaluation is opt-in and user assessed. The runner never chooses a backend automatically, and a completed model response remains unscored until a human or calibrated judge applies the versioned rubric. Cursor supports prepared manual evaluation; automated Cursor execution remains disabled until a stable CLI contract is available.

See [.forge-skill/forge/README.md](.forge-skill/forge/README.md), [.forge-skill/forge/BOOTSTRAP.md](.forge-skill/forge/BOOTSTRAP.md), and [.forge-skill/forge/scripts/README.md](.forge-skill/forge/scripts/README.md) for architecture, project linking, and advanced commands.

## Publication Note

This project is distributed under the MIT License; see [LICENSE](LICENSE).
