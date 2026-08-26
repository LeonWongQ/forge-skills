# BOOTSTRAP.md

## Purpose

When other projects symlink to this repo's `.claude/forge/` and `.claude/skills/`, their `CLAUDE.md` has no entry point into the forge discovery chain. This file provides:

1. The bootstrap snippet to paste into other projects' `CLAUDE.md`
2. Setup instructions for cross-project symlinks
3. Reference material explaining the forge system

---

## When to Use Forge

Activate forge when the task is meaningfully engineering-oriented:

- Code review, debugging, refactoring, optimization
- Backend testing, UI test planning, test reporting
- Structured implementation planning, incident analysis
- Architecture-oriented explanation, error analysis
- Migration planning, compatibility assessment

For trivial tasks, use only the smallest relevant subset — or skip forge entirely for quick questions.

---

## Setup (in each target project)

### Recommended: use the link tool

From the Forge source repository on Windows, run:

```bat
install-link-forge.bat <target_project_path> --tool <claude|cursor|codex>
```

The link tool creates directory junctions without replacing existing real directories:

| Tool | Linked directories |
|------|--------------------|
| Claude Code | `.claude\forge`, `.claude\skills` |
| Cursor | `.cursor\forge`, `.cursor\skills`, `.cursor\rules` |
| Code X | `.codex\forge`, `.codex\skills`, `.codex\rules` |

`rules` is linked for Cursor and Code X only when the source rules directory exists. If a target path is already a real directory, the tool reports a conflict and leaves it unchanged.

`install-link-forge.bat` first requires Python 3.11+ before it creates any project directories or junctions, then verifies the resulting junction targets before it reports success. This uses the source checkout and does not require `pip install`, Forge dev dependencies, a global `forge` executable, or manual PATH configuration.

### Cross-session Forge Runtime

Forge does not install a Claude Code `SessionStart` Hook and does not automatically scan, prompt for, or resume Runtime work when a session starts. Ordinary suspended work remains a Claude Code native background-agent concern.

For an explicitly persisted Forge Runtime, the active client checks the current project's `.forge-runtime/` only when the user asks to view or continue it. It presents only valid nonterminal candidates, asks which one to continue, then consumes the selected Runtime as a one-time handoff. That selection does not modify, delete, or archive any other Runtime.

Older Forge installs may have written a marker-owned SessionStart entry. Uninstall compatibility removes only that known Forge entry; it does not modify user-owned Hooks, `.forge-runtime/`, or `.gitignore`.


### Advanced: create junctions manually

Use this only when the link tool cannot be used. Replace `<forge-source-root>` with the local source checkout; avoid copying the example as a machine-specific absolute path.

```bat
mklink /J .claude\forge  <forge-source-root>\.claude\forge
mklink /J .claude\skills <forge-source-root>\.claude\skills
```

### Add the bootstrap snippet

Paste this snippet at the TOP of the target project's `CLAUDE.md`:

```markdown
<!-- FORGE-BOOTSTRAP — symlinked forge entry point. Docs: .claude/forge/BOOTSTRAP.md -->

## Forge Engineering System

Core rule: **available modules ≠ active modules** — only task-relevant modules activate.
The system must remain selectively activated. Do not collapse it back into an always-on mega-prompt.

### Discovery sequence
1. `.claude/forge/CLAUDE.md` — universal principles, invariants, decision hierarchy
2. `.claude/forge/AUTOLOAD.md` — selective activation and host ownership gate
3. Explicit `/skill` and Forge Runtime handling remain host-owned; then apply `registry/skill-routing.json` `ask_policy`
4. Forge-first skill match: `.claude/skills/` — pre-composed task entry points
5. Pack match: `.claude/forge/packs/` — technology-specific fast paths
5. Manual routing: `.claude/forge/runtime/router.md` — behavior + domains + workflow + template + checklists

### Key rules
- **Engineering tasks MUST route** through the host ownership gate and then the applicable Forge skill/pack path before free-form response. Direct free-form only for trivial questions.
- **Explicit/native boundary**: preserve Runtime lifecycle intent and explicit `/skill`; route native-first specialist capabilities according to `registry/skill-routing.json` `ask_policy`.
- **Forge-first**: use only the policy-approved Forge skills for general engineering work (review, debug, plan, refactor, etc.).
- **Pack-first**: prefer packs for technology-specific scenarios (Spring review, Playwright debug, etc.)
- **Minimal-first**: start small — kernel + one behavior + one domain + default template + general quality checklist. Only deepen when required.
- **Project-local truth**: this project's real code, configs, and runtime behavior take priority over forge template assumptions.
- **Expand only when justified**: add domains, deepen workflow, or switch templates when the task grows in risk, uncertainty, or scope.
- **Ambiguous tasks**: if the user says "先看看" / "look into it" / "explore", prefer `skill: explore` — it maps fuzzy exploration into structured discovery before committing to a specific mode.

### Anti-patterns
- Treating forge as one giant always-active prompt
- Activating all domains "just because they exist"
- Forcing full workflows into small tasks
- Skipping skill or pack match when a task clearly fits one
- Preferring generic guidance over concrete local evidence

### Quick reference
| Task | Entry | | Task | Entry |
|------|-------|-|------|-------|
| Review code | skill: `code-review` | Debug | skill: `debug` |
| Plan | skill: `plan` | Error analysis | skill: `error-analysis` |
| Report | skill: `report` | Explain | skill: `explain` |
| Refactor | skill: `refactor` | Optimize | skill: `optimize` |
| Document | skill: `document` | Explore/scope | skill: `explore` |
| Test design | skill: `test-design` | Test implement | skill: `test-implementation` |
| Incident | skill: `incident` | Migration | skill: `migration` |
| Spring review | pack: `spring-review` | Flaky test | pack: `playwright-debug` |
| Redis incident | pack: `redis-incident` | Java refactor | pack: `java-refactor` |
| Test report | pack: `general-test-report` | Test plan | pack: `general-test-plan` |

---

<!-- Everything below is this project's own documentation -->
```

---

## Source Structure

```
.claude/
├── CLAUDE.md          ← project entry point (the bootstrap snippet above)
├── forge/             ← modular engineering architecture
│   ├── CLAUDE.md      ← kernel: universal principles, invariants, decision hierarchy
│   ├── AUTOLOAD.md    ← selective activation policy, routing gate
│   ├── BOOTSTRAP.md   ← this file: cross-project setup guide
│   ├── engine/        ← workflow stages (discover → evidence → ... → delivery)
│   ├── behaviors/     ← task modes (review, debug, refactor, optimize, document, explain)
│   ├── domains/       ← technical expertise (java, spring, redis, playwright, mysql, testing)
│   ├── checklists/    ← quality gates (general, review, debug, refactor, delivery, verification)
│   ├── registry/      ← machine-readable module catalog + schemas + skill-routing
│   ├── runtime/       ← router, runtime contract
│   ├── packs/         ← technology-specific fast paths
│   ├── general-test/  ← test plan & report pack assets
│   └── scripts/       ← validation & cross-reference tools
├── skills/            ← skill definitions (SKILL.md per skill)
└── rules/             ← rule files
```

---

## Why not merge CLAUDE.md files?

| Hub CLAUDE.md | Project CLAUDE.md |
|---------------|-------------------|
| Forge entry point (bootstrap snippet) | Project-specific codebase guide |
| Delegates to forge kernel for everything else | Tech stack, conventions, architecture |
| Same snippet every project pastes | Unique to each project |

The bootstrap snippet delegates discovery to forge's own files — symlinks keep them current, hub updates propagate automatically, and each project's `CLAUDE.md` stays lean.
