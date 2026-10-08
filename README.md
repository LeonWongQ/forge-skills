# Forge Skills

<!-- forge-facts: skills=33 version=1.2.1 route-regression-count=81 skill-eval-case-count=49 skill-eval-skill-count=33 -->

An engineering toolkit for Codex, Claude Code, and Cursor, with 33 Skills for
review, debugging, implementation, planning, testing, and architecture.
Forge provides deterministic routing and validation, plus an opt-in learning
workflow that improves project-specific guidance from reviewed results.

## Quick Start

Requires Python 3.11+. Standalone `page-test` also requires Node.js 22+ and an
existing Chrome, Edge, or Chromium installation.

Install from this checkout on Windows:

```powershell
install-skills.bat --client codex --scope global
```

On macOS or Linux:

```bash
python .forge-skill/forge/scripts/sync-agent-skills.py --client codex --scope global
```

- Replace `codex` with `claude` or `cursor` for another host.
- For a project installation, use `--scope project --project <path>`.
- Add `--check` to preview changes or `--uninstall` to remove links from this checkout.

The installer preserves existing files and conflicting links. It links Skills
alongside shared `forge` and `forge-data` directories. Runtime data is isolated
by project and Skill under `forge-data`.

## Project Learning

Learning improves Skill instructions; it does not train model parameters or
rewrite the global Skill.

```text
Collect → Review evidence → AI Summary → Review Summary
        → Project Overlay → Evaluate → Publish → Manually activate
```

Collection is disabled by default. Copy
[config.example.json](.forge-skill/learning/config.example.json) to
`.forge-skill/learning/config.json` and list the Skills to enable.
Use the `learning-collector` Skill to open the local dashboard, which supports
English and Simplified Chinese.

AI Summaries process eligible reviewed evidence in bounded batches. Generated
Overlays are read-only; copies can be edited. Publication and activation are
separate actions. Invalid Overlay data leaves the global Skill unchanged.
Collection is best-effort, and real model evaluation requires explicit setup
and assessment.

See the [learning lifecycle](.forge-skill/skills/learning-collector/references/lifecycle.md)
for configuration, review, evaluation, and recovery details.

## Development

Install development dependencies from `.forge-skill/forge`, then run the full
validation gate:

```bash
python .forge-skill/forge/scripts/run-local-checks.py --full
```

## Documentation

- [Forge overview and commands](.forge-skill/forge/README.md)
- [Project setup](.forge-skill/forge/BOOTSTRAP.md)
- [Scripts reference](.forge-skill/forge/scripts/README.md)

## About the Maintainer

Built by Leon Wong, an engineer who enjoys exploring emerging technologies,
developing ideas, and testing them through hands-on practice.

Licensed under the [MIT License](LICENSE).
