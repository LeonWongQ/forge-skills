# Forge Skills

<!-- forge-facts: skills=33 version=1.2.1 route-regression-count=81 skill-eval-case-count=49 skill-eval-skill-count=33 -->

Forge Skills is a modular engineering Skill collection for Codex, Claude, and Cursor. It combines focused Skill entrypoints with deterministic routing, reusable engineering guidance, validation tooling, and opt-in LLM behavior evaluation.

## What Forge Includes

- **33 focused engineering Skills** for review, debugging, implementation,
  planning, testing, architecture, documentation, and related workflows.
- **Deterministic routing and validation** so Skill selection, registry links,
  paths, contracts, and evaluation assets can be checked before release.
- **Cross-host installation** for Codex, Claude Code, and Cursor from one source
  checkout, at either global or project scope.
- **Project-isolated runtime data** under `forge-data`, separated by project ID
  and Skill rather than mixed into source repositories.
- **An opt-in Skill training loop** that turns reviewed execution evidence into
  versioned, project-specific guidance without rewriting the global Skill.

## Requirements

- Python 3.11 or later for Forge validation and installation tooling; CI verifies 3.11, 3.12, and 3.13.
- Node.js 22 or later for the standalone `page-test` runtime; CI verifies Node.js 22.
- An existing Chrome, Edge, or Chromium installation for standalone browser work. The project never installs a browser automatically.

## Install Skills

The installer creates only missing links and preserves existing files, directories, and conflicting links. Every global or project installation links the shared `forge` and `forge-data` companions beside the target `skills` directory.

Forge-generated runtime data is stored separately under `forge-data`, partitioned
by project ID and Skill. Project repositories retain only lightweight project
identity and local configuration files. Learning configuration is ignored by
Git, while databases, summaries, evaluation artifacts, service state, and paused
Runtime documents stay outside the tracked source tree.

## Project-Scoped Skill Training

Forge can train a Skill by improving its external instructions, checks, and
output behavior from reviewed results. It does **not** train model parameters.
The global Skill remains unchanged; the final artifact is a versioned Overlay
that can supplement one Skill in one project.

The lifecycle is deliberately gated:

```text
opt-in Skill
  -> collect final result
  -> human record review
  -> versioned Summary
  -> optional LLM refinement
  -> human Summary review
  -> project Overlay
  -> evaluation and publication
  -> manual activation
  -> reviewed feedback and automatic disabling
```

Collection is disabled by default. Copy
`.forge-skill/learning/config.example.json` to
`.forge-skill/learning/config.json`, then explicitly list the Skills that may
collect data:

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

The local dashboard provides three focused workspaces:

- **Review dashboard** — inspect, search, edit, exclude, or delete collected
  records, with 20-item pagination and project/Skill filtering.
- **Summary management** — generate versioned summaries, inspect source
  evidence, review individual rules, and explicitly request LLM refinement.
- **Overlay management** — combine reviewed Summary versions into a
  project-specific Overlay, review and evaluate it, publish it, then activate it
  as a separate manual action.

The interface supports English and Simplified Chinese. The selected language is
shared across pages and also controls the human-readable output language of LLM
refinement and Overlay generation; collected evidence is preserved as written.

Start the local review dashboard when needed:

```text
forge ask "启动学习审核页面"
forge ask "关闭学习审核服务"
```

### Quality and Safety Boundaries

- Deterministic extraction requires repeated independent evidence for ordinary
  candidates; explicit learning signals or human review notes may admit a
  single-record candidate.
- LLM refinement first classifies every candidate as `KEEP`, `DISCARD`, or
  `CONFLICT`, then synthesizes only retained evidence into a new Summary version.
  It never overwrites the source version or activates the result.
- Evaluation compares Baseline and Candidate behavior using compatible fixed
  cases. Publication does not activate an Overlay, and only one Overlay can be
  active for a project and Skill.
- Runtime application fails open: missing or invalid Overlay data leaves the
  global Skill unchanged.
- Once an active Overlay has more than 10 reviewed results, an exclusion rate
  above 30% disables that exact Overlay. Forge does not automatically activate a
  replacement.
- Direct-host collection remains best-effort because current hosts do not expose
  a universal after-response hook. It must not be described as 100% capture.

Machine-local settings live in `forge-data/runtime.json`; API credentials remain
in environment variables. Project learning configuration remains local at
`.forge-skill/learning/config.json` and is intentionally excluded from Git. See
the [RC1 test guide](.forge-skill/forge/docs/SKILL-TRAINING-RC1.md) for the full
workflow, acceptance evidence, and current evaluation limitations.

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
