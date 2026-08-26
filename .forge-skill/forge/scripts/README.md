# Scripts

<!-- forge-facts: skill-eval-case-count=37 skill-eval-skill-count=31 -->

## Purpose

This directory contains validation and maintenance scripts for the machine-readable layer of the repository.

These scripts help ensure that:
- registry files match their schemas
- registry-declared paths exist
- cross-references between registries remain valid

This is the first step toward CI-backed repository hardening.

---

## Local Quality Gate

`run-local-checks.py` is the authoritative, non-mutating local gate. It resolves its Forge root from the script location, so it works from the source tree or through the supported directory junction deployment.

It has two modes:

- `--quick`: commit-time skill quality, behavior-corpus integrity, and all eight deterministic Forge validation checks
- `--full` (default): quick checks plus route regression, documentation facts, and pytest

Both modes begin with `check-text-integrity.py`, which decodes project-owned text as strict UTF-8
and rejects replacement characters, NUL bytes, and high-confidence mojibake fragments. Generated
evaluation artifacts, dependency trees, caches, and Git metadata are excluded. This protects valid
Chinese skill triggers while catching actual encoding damage; Windows wrappers also select UTF-8
console and Python I/O modes.

Both modes also run `check-sensitive-content.py` over public source files. It rejects common
credential and private-key formats, private-network addresses, and machine-specific user paths.
Ignored local evaluation, test, dependency, and agent settings directories are excluded from this
check because they are not publication artifacts.

## Codex Skill Sync

`sync-codex-skills.py` exposes project-owned Forge skills in an existing Codex global directory without replacing its `skills/.system` directory or any existing same-name skill. It creates only missing child Junctions for `forge` and directories containing `SKILL.md`.

```powershell
python .forge-skill/forge/scripts/sync-codex-skills.py --check
python .forge-skill/forge/scripts/sync-codex-skills.py
python .forge-skill/forge/scripts/sync-codex-skills.py --watch
```

Healthy links are collapsed into a summary by default. Add `--verbose` to list every link,
or `--json` for complete machine-readable actions. `--check` returns success when every
existing Junction already targets this project source and fails only for missing links,
conflicts, or missing sources.

`--watch` checks every 10 minutes by default and creates missing Junctions for newly created skill folders. Use `--interval <seconds>` to override it. It never removes or overwrites a global path.

## Common Skill Installation

`sync-agent-skills.py` exposes each project-owned skill to Codex, Claude, or Cursor at either
global or project scope. On Windows it creates directory Junctions; on POSIX it creates directory
symlinks. Existing files, directories, unrelated skills, and links to another source are reported
as conflicts and are never replaced.

Inspect a global installation without changing anything:

```powershell
python .forge-skill/forge/scripts/sync-agent-skills.py --client codex --scope global --check
python .forge-skill/forge/scripts/sync-agent-skills.py --client claude --scope global --check
python .forge-skill/forge/scripts/sync-agent-skills.py --client cursor --scope global --check
```

Install globally for the selected client:

```powershell
install-skills.bat --client claude --scope global
install-skills.bat --client cursor --scope global
```

Install into one existing project:

```powershell
install-skills.bat --client cursor --scope project --project D:\work\my-project
install-skills.bat --client claude --scope project --project D:\work\my-project
```

Resolved skill roots are:

| Client | Global | Project |
|---|---|---|
| Codex | `~/.codex/skills` | `<project>/.codex/skills` |
| Claude | `~/.claude/skills` | `<project>/.claude/skills` |
| Cursor | `~/.cursor/skills` | `<project>/.cursor/skills` |

Project scope requires an existing `--project` directory, preventing a typo from creating an
unexpected project tree. `--target` is an advanced exact-skills-directory override. Add `--json`
for machine-readable output, or `--watch` to link new source skills as they appear. In `--check`
mode, exit code `1` means links are missing or conflicts exist; no directories are created.
Use `--uninstall` to remove only links that still point to this source checkout; combine it with
`--check` to preview removals. User-owned directories and links to other sources are preserved.

The older `sync-codex-skills.py` remains available for backward compatibility and also manages
the separate `~/.codex/forge` link. The common installer manages skills only, so it can coexist
with unrelated client configuration and plugins.

Full mode runs, fail-fast:

1. `python scripts/check-text-integrity.py`
2. `python scripts/check-sensitive-content.py`
3. `python scripts/check-skill-quality.py`
4. `python scripts/check-skill-eval-corpus.py`
5. `python -m forge_cli --root <forge-root> validate` (all eight validation checks)
6. `python scripts/check-route-regression.py`
7. `python scripts/check-documentation-facts.py`
8. `python -m pytest`

Quick mode runs only steps 1-3.

Use the platform wrappers to invoke it:

- Windows: `scripts/run-local-checks.bat`
- POSIX/Git Bash: `scripts/run-local-checks.sh`

The default gate does not generate reports. Use `validate --report` or `doctor --report` explicitly for diagnostic artifacts.

## Current Scripts

### `validate-registry.py`
Validates selected registry files against JSON Schema.

Current coverage:
- `registry/modules.json`
- `registry/workflows.json`
- `registry/compositions.json`
- `registry/contracts.json`
- `registry/skills.json`, `skill-routing.json`, `behaviors.json`, `domains.json`,
  `templates.json`, `checklists.json`, `reports.json`, `project.json`,
  `packs.json` (index), `route-regression.json`, `template-outputs.json`

This command is a standalone schema validator; `run-local-checks.py` uses the
Forge CLI as the authoritative complete validation gate.

### `validate-packs.py`
Validates every pack listed in `registry/packs.json` against
`registry/schemas/packs.schema.json`.

### `check-module-paths.py`
Checks that all module paths declared in `registry/modules.json` exist in the
repository. Also sandboxes paths so a registered path that escapes the workspace
root (e.g. `../../etc/passwd`) is flagged, not silently passed.

### `check-cross-references.py`
Checks cross-reference integrity across registries.

Current coverage:
- workflow -> engine stage references (`stages` field)
- compositions -> behavior/domain/workflow/template/checklist references
- skills -> behavior/workflow/template/domain/checklist references
- default workflow existence

### `check-pack-references.py`
Verifies that pack references (behaviors, domains, templates, checklists,
workflows, reports, `routing.preferred_skill`) all point to known ids.

### `check-route-regression.py`
Runs the route/recommend regression cases in `registry/route-regression.json`
against the live CLI and asserts skill/pack/confidence match expectations.

### `check-skill-eval-corpus.py`
Validates the versioned forward-test prompts and rubrics in
`evals/skill-behavior-cases.json`. This checks corpus integrity only; a real model or
agent run is still required to evaluate behavior.

### Skill behavior evaluation

`run-skill-evals.py` prepares the versioned behavior corpus for any LLM client and can optionally
execute them through an explicitly selected Codex or Claude CLI adapter. LLM evaluation is a
user decision: the runner never selects a backend automatically, and execution requires both
`--backend` and `--confirm-llm-evaluation`. Claude automation additionally requires
`--confirm-claude-unisolated-filesystem` because its CLI tool restrictions do not provide
OS-level read isolation. Corpus validation and fixture preparation are fully
model-free; they do not launch an LLM, browser, or installer.

Prepare fixtures and prompts for inspection or manual use in Claude, Cursor, Codex, or another
client without launching an LLM:

```powershell
python .forge-skill/forge/scripts/run-skill-evals.py --prepare .skill-eval/prepared
```

When the user chooses automated execution, check only that selected backend:

```powershell
python .forge-skill/forge/scripts/run-skill-evals.py --list-backends
python .forge-skill/forge/scripts/run-skill-evals.py --list-backends --json
python .forge-skill/forge/scripts/run-skill-evals.py --preflight --backend codex
python .forge-skill/forge/scripts/run-skill-evals.py --preflight --backend claude
```

Backend listing and preflight do not invoke a model. Listing reports local command availability,
automation support, containment, and authentication behavior; JSON output is available for tools.
Preflight reports applicable local
authentication prerequisites without printing credential values. A successful preflight cannot
guarantee network availability; execution failures remain recorded in `run.json`. Preflight also
runs the selected backend's `--version` command. On Windows, an explicitly selected native Codex
executable must have its matching `codex-windows-sandbox-setup.exe` beside it; an incomplete or
version-mismatched CLI installation fails before any model call.

Execute only after the user assesses and approves LLM use, selecting the provider and candidate
explicitly:

```powershell
python .forge-skill/forge/scripts/run-skill-evals.py --output .skill-eval/candidate --backend claude --confirm-llm-evaluation --confirm-claude-unisolated-filesystem --label candidate-v1 --model <model-id>
```

The Codex adapter uses `codex exec --ephemeral` with the corpus `read-only` or
`workspace-write` sandbox. The Claude adapter reuses the installed CLI session, disables session
persistence, uses `dontAsk` for read-only cases and `acceptEdits` for writable cases, and restricts
available tools to fixture file operations. On Windows it resolves the installed native
`claude.exe` behind the command shim so process-tree timeouts remain enforceable. Its tool
restrictions are not equivalent to an OS-level sandbox. Fixture snapshots detect writes but cannot
detect reads outside the fixture, so Claude results are recorded as not OS-isolated and require the
additional explicit acknowledgement above. Selected skill files, bundled references, and shared Forge guidance are staged into
the disposable fixture; evaluation corpora, graders, tests, and reports are excluded to prevent
answer leakage. Automated `run.json` artifacts are explicitly ineligible as trusted isolated
benchmark runs because fixture-only read scope is not verified, and should not be produced from a
sensitive workspace. Cursor automated execution fails closed until a stable `cursor-agent` CLI
contract is available; use `--prepare` for manual Cursor evaluation. No adapter installs a CLI,
browser, dependency, or credential.

Each corpus case declares `requires_capabilities`. The runner compares those requirements with the
selected backend before preflight and model execution. The Claude adapter intentionally exposes no
shell or browser command, so actual Playwright execution is recorded as `unsupported_backend`
rather than a model failure. Authorization-gate cases remain runnable because they must stop before
execution. Included environment gates run only when their declared host condition is detected;
otherwise they are recorded as `environment_gated_not_run`. Browser detection checks existing PATH
and standard installation locations and never installs anything. Both statuses remain visible in `run.json`
and are excluded from `decisions.template.json` and the process exit failure set.

For a browser-capable backend, staging copies the already-present skill-owned `playwright-core`
runtime into the disposable fixture only for cases that declare the `browser` capability. It never
installs a package or browser. If that local runtime is absent, staging fails closed with a runner
error instead of advertising unusable browser capability.

`--backend-command` overrides the selected adapter command. The former `--codex-command` flag
remains accepted as a compatibility alias when `--backend codex` is also explicit; it never
selects Codex or supplies user consent by itself.

Both paths write `decisions.template.json`. Execution also writes `run.json`, response,
stdout, and stderr artifacts. A successful model response is `completed_unscored`, not a
pass: fill every `null` rubric decision with a Boolean based on a human review or a calibrated
judge, then score it:

Consolidate initial and retry runs into one auditable human-review package without invoking another
model. Input order is attempt order; the package retains every attempt and selects the latest
successful response for each case. Completed retries must use the same backend, model, and user
configuration:

```powershell
python .forge-skill/forge/scripts/prepare-skill-eval-review.py --run <run-1>/run.json --run <run-2>/run.json --output .skill-eval/manual-review
```

The output contains `review.md`, an editable `decisions.json`, an untouched
`decisions.template.json`, and a scorer-compatible consolidated `run.json`. The command rejects
duplicate cases within one run, completed retries from a different candidate identity, missing
responses, and non-empty output directories. Timeout and runner-failure attempts remain in each
selected result's `attempt_history`; cases without a completed response are omitted from scoring.
A historical corpus hash difference is retained in the source manifest instead of being hidden;
review always displays the current versioned prompt and rubric.

```powershell
python .forge-skill/forge/scripts/score-skill-evals.py --run .skill-eval/candidate/run.json --decisions .skill-eval/candidate/decisions.json --output .skill-eval/candidate/scored.json
```

Freeze the reviewed evidence as a portable baseline. Pending human decisions are preserved and
reported explicitly. When every decision is Boolean, freezing applies the same explicit scorer and
writes `scored.json`; failed rubric cases remain valid baseline evidence and are not rejected:

```powershell
python .forge-skill/forge/scripts/freeze-skill-eval-baseline.py --package .skill-eval/manual-review --output .skill-eval/baselines/baseline-v1 --label baseline-v1
```

After running and reviewing a candidate on the same cases, compare execution status, subjective
quality, and latency as independent dimensions:

```powershell
python .forge-skill/forge/scripts/compare-skill-evals.py --baseline .skill-eval/baselines/baseline-v1 --candidate .skill-eval/candidate/scored.json --output .skill-eval/comparisons/candidate-v1
```

The comparator verifies every frozen artifact hash and the corpus hash, rejects duplicate, missing,
or extra cases, and refuses candidate evidence from a different corpus. It reports execution and latency for unscored runs,
but keeps the gate at `pending_human_scoring` until both baseline and candidate contain explicit
`pass`/`fail` rubric outcomes. Deterministic execution regressions fail immediately even while
subjective scoring is pending. A latency improvement never offsets a quality or execution regression.

Cases marked `environment_gated` are excluded by default and require explicit
`--include-gated`. Select individual cases with repeatable `--case <case-id>`. Use
`--ignore-user-config` only with the Codex backend when its defaults are intentionally required;
authentication can only be confirmed during execution. Runner statuses distinguish
`backend_unavailable`, `sandbox_unavailable`, `timeout`, `runner_error`, and deterministic
`safety_failure` from unscored successful execution. A sandbox-helper launch failure aborts the
remaining selected cases and records them in `execution_abort.not_run_case_ids` instead of
misclassifying a fluent environment-error response as a completed evaluation.

Retry only selected timeout cases with a larger, explicitly recorded budget by repeating
`--case` and setting `--timeout-multiplier`. The multiplier applies to each case's declared
timeout only for LLM execution; it does not alter the versioned corpus or the default behavior:

```powershell
python .forge-skill/forge/scripts/run-skill-evals.py --output .skill-eval/timeout-retry --backend codex --confirm-llm-evaluation --case <case-id> --timeout-multiplier 2
```

### `check-documentation-facts.py`
Validates explicitly marked inventory and validation facts in the primary Forge entry documents against the current registries and `forge_cli.constants.ALL_CHECKS`.

### `run-local-checks.py`
Runs the authoritative local quality gate without writing report artifacts. Use `--quick` for
commit-time skill and deterministic Forge validation. With no mode flag, or with `--full`, it
also runs route regression, documentation-facts validation, and the complete pytest suite.
`.github/workflows/quality-gate.yml` runs this full deterministic gate for pushes and pull
requests. It deliberately does not invoke `run-skill-evals.py`, require provider credentials, or
install browsers.

### `check-text-integrity.py`
Scans project-owned text files using strict UTF-8 decoding and fails on invalid byte sequences,
Unicode replacement characters, NUL bytes, or known high-confidence mojibake fragments. It skips
dependencies, generated evaluation artifacts, temporary test data, caches, and Git metadata.

### `check-sensitive-content.py`
Scans the files intended for publication and fails on high-confidence credential formats, private
key headers, private IPv4 addresses, absolute Windows/POSIX user-home paths, email addresses, and
the repository's prohibited organization or personal identifiers. It is deterministic and offline;
it does not upload source or invoke a third-party scanner.

### `check-report-freshness.py`
Compares committed `validate-report.json` / `doctor-report.json` against freshly
generated copies using the full stable report contract: command, summary, ordered checks,
and diagnostic messages. Machine-specific roots and execution durations are ignored; a
missing or malformed fresh report is a failure rather than silently "up-to-date".

---

## Recommended Usage

Run locally:

```bash
python scripts/validate-registry.py
python scripts/validate-packs.py
python scripts/check-module-paths.py
python scripts/check-cross-references.py
python scripts/check-pack-references.py
python scripts/check-route-regression.py
```

Or run the complete non-mutating gate in one go:

- Windows: `scripts/run-local-checks.bat`
- POSIX:   `scripts/run-local-checks.sh`

Append `--quick` to either wrapper for commit-time feedback.

For schema validation, install:

```bash
pip install jsonschema
```

---

## Short Reminder

These scripts validate repository integrity.
They do not replace architectural review, but they reduce maintenance drift.
