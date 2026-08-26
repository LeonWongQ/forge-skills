# Changelog

## Unreleased

### Changed
- LLM evaluation runs now persist backend-reported Codex token usage per case and in aggregate, mark unknown Relay pricing as `cost_unavailable`, and keep all backend fixtures under the output-local `.fixtures` directory.
- Added a deterministic sensitive-content gate for common credential formats, private keys, private-network addresses, and machine-specific user paths; local evaluation, test, dependency, and agent settings artifacts are excluded from publication through `.gitignore`.
- GitHub quality-gate setup now runs on Windows, Ubuntu, and macOS with Node.js 22 and restores the pinned `playwright-core` library with lifecycle scripts disabled, without installing a browser.
- Local quality gates now support a fast `--quick` commit mode while preserving the complete default/`--full` validation contract.
- Pre-commit uses the quick gate; platform wrappers forward mode arguments.
- Codex skill synchronization recognizes healthy Windows Junctions and collapses unchanged links into a concise summary; `--verbose` retains full text output.
- Expanded the versioned skill behavior forward-test corpus to 14 cases across 10 core Skills, with deterministic corpus-integrity and coverage checks in both quick and full quality gates.
- Hardened `implement` retry guidance: effectful retries now require evidence of pre-commit failure, idempotency, or transactional duplicate handling, and verification must distinguish repeated calls from duplicate committed effects.
- Added isolated skill behavior preparation, execution, explicit-rubric scoring, gated-case opt-in, backend preflight, and auditable run artifacts; successful executions remain unscored until reviewed by a human or calibrated judge.
- Made LLM skill evaluation provider-neutral and explicitly user-approved: preparation is model-free, execution requires a selected backend plus acknowledgement, Codex and Claude reuse existing authentication, and unsupported Cursor automation fails closed without installing anything.
- Added human and JSON backend discovery, retained `--codex-command` as a consent-preserving compatibility alias, and introduced a mandatory deterministic-only GitHub Actions quality gate with no LLM or browser setup.
- Added a common non-destructive skill installer for Codex, Claude, and Cursor with explicit global/project scope, dry-run checks, JSON output, optional watching, Windows Junctions, POSIX symlinks, and typo-safe project targeting.
- Hardened Claude skill evaluation with native Windows process resolution, bounded timeout cleanup, output-local disposable fixtures, explicit read/edit permission modes, complete non-rubric skill staging, evidence-first prompt framing, protected guidance snapshots, and incremental run persistence.
- Claude automated evaluation now requires separate acknowledgement of its non-OS-isolated read boundary; all automated backends record unverified fixture-only read scope and remain ineligible as trusted isolated benchmarks.
- Skill and Junction installers roll back links created by a failed invocation, including verification and manifest failures; Runtime consumption restores its source JSON without overwriting a concurrently created runtime when claim cleanup fails.
- Sensitive-content validation fails closed on unreadable or non-UTF-8 public files, and page extraction prioritizes semantic content containers before falling back to `body`.

## v1.2.1 - Runtime Safety and Codex Deployment Refinements

### Fixed
- Runtime suspension now creates persisted task files exclusively, preventing concurrent writes from overwriting an existing task.
- Contract compatibility validation fails closed when `jsonschema` is unavailable.
- Codex skill synchronization rejects invalid watch polling intervals at argument parsing time.

### Changed
- Global Codex Forge fallback preserves logical installation paths while Runtime state remains in the current project's `.forge-runtime` directory.
- Consumer-facing Runtime and project metadata paths are relative and do not expose an installation target.

## v1.2.0 — Operational Validation, Compatibility, and Routing Calibration

### Added
- `forge validate-output` validates a supplied JSON document against the output schema registered for a canonical template ID.
- `forge validate --check contracts` validates fixture-backed baseline/current API and event JSON Schema compatibility directions.
- `domain.api_event_contracts`, `checklist.contract_compatibility`, and `skill.contract_compatibility` provide focused producer/consumer assessment guidance.
- `domain.observability_reliability`, `checklist.release_readiness`, `skill.release_readiness`, and `pack.release_readiness` add evidence-based production go/no-go assessment.
- `scripts/run-local-checks.py` is the non-mutating, junction-aware local quality gate for full seven-check validation, routing regression, documentation-facts validation, and pytest.
- A categorized route/recommend corpus with explicit matched, nullable pack, bounded confidence, and optional diagnostic expectations.

### Changed
- Windows and POSIX local-check wrappers now delegate to the same Python gate and no longer depend on the compatibility shim or generate reports by default.
- Routing confidence is policy-driven for ordinary, unmatched, tie-break, and `--prefer` fallback outcomes.
- Route and recommend JSON now expose normalized confidence diagnostics, including pre-cap/final confidence, selection mode, caps, evidence counts, and meaningful tie-break margins.
- Semantic validation now checks all routing bias-rule keyword-set references, generic trigger skill references, and confidence-policy gap ordering.

### Compatibility
- No module IDs, CLI command names, or existing top-level response fields were removed.
- Pack selection continues to shape composition, but does not promote skill confidence under the v1 policy.

---

## v1.1.1 — Registry Governance Milestone

### Overview
Completed schema coverage and CLI validation wiring for all core registries.
The `forge validate` toolchain now passes 5/5 checks with 0 warnings and 0 errors.

### Added
- `engine.schema.json` — schema for the deprecated engine registry migration pointer
- `behaviors.schema.json`, `domains.schema.json`, `templates.schema.json` — behavior/domain/template registry schemas
- `checklists.schema.json`, `reports.schema.json` — checklist and report registry schemas
- `skill-routing.schema.json`, `skills.schema.json` — skill routing and skill index schemas
- `project.schema.json`, `packs-index.schema.json` — project metadata and pack index schemas

### Changed
- **`forge.py` `REGISTRY_SCHEMA_CANDIDATES`** — wired all 13 registry→schema pairs
- **`forge.py` `REGISTRY_WITHOUT_SCHEMA`** — reduced to only `template-outputs.json`
- **`forge.py` `check_paths`** — fixed path resolution for `.claude/`-prefixed paths (now resolves from project root instead of forge root)
- **All 5 new skills** (`test_design`, `incident`, `test_implementation`, `migration`, `explore`) are fully registered with keyword sets, bias rules, and tie-break rules
- **All 6 packs** have complete `routing` blocks in their JSON files — `PACK_ROUTE_RULES` builtin fallback is now a safety net only

### Validation Status
```
Summary: ok=True, total_checks=5, warnings=0, errors=0
  [PASS] registry  — 13 SCHEMA_VALID, 0 errors
  [PASS] paths     — All registered module paths exist
  [PASS] refs      — All checked references are valid
  [PASS] packs     — 6 PACK_SCHEMA_VALID
  [PASS] pack-refs — All checked pack references are valid
```

### Task 2: skills.json Final Verification (30/30 fields)

All 5 new skills verified with correct field values:

| Skill | name | behavior | workflow | context | template |
|-------|------|----------|----------|---------|----------|
| `skill.test_design` | test-design | null | workflow.full_default | inherit | template.test_plan |
| `skill.incident` | incident | behavior.debug | workflow.debug_analysis | fork | template.debug_report |
| `skill.test_implementation` | test-implementation | null | workflow.full_default | fork | template.test_plan |
| `skill.migration` | migration | null | workflow.full_default | fork | template.implementation_plan |
| `skill.explore` | explore | null | workflow.blocked_task | inherit | template.default |

All cross-references validated: workflows ✓, templates ✓, checklists ✓, behaviors ✓, domains ✓

Route smoke test results (5/5 correct):
- "帮我设计测试方案" → `skill.test_design` + `pack.general_test_plan` (high)
- "帮我补一组单元测试" → `skill.test_implementation` (low, trigger gap noted)
- "给我一个 spring boot 升级迁移方案" → `skill.migration` (high)
- "生产环境服务异常，帮我做事故分析" → `skill.incident` (high)
- "先帮我摸清楚这个模块现状" → `skill.explore` (high)

### Task 3: Pack Routing — Data-Driven Verification (12/12 regression pass)

All 6 packs have complete `routing` blocks. `forge.py` `route_pack()` uses strict filtering:
mismatched `preferred_skill` → pack is skipped unless in `PACK_CROSS_SKILL_ALLOWED`.

Route regression (6/6 skill+pack pairs correct):
- Spring review → `skill.code_review` + `pack.spring_review`
- Playwright flaky → `skill.debug` + `pack.playwright_debug`
- Redis incident → `skill.incident` + `pack.redis_incident`
- Java refactor → `skill.refactor` + `pack.java_refactor`
- Test plan → `skill.test_design` + `pack.general_test_plan`
- Test report → `skill.report` + `pack.general_test_report`

Recommend regression (6/6 correct):
- "生成测试报告" → `skill.report`, "Playwright e2e CI 不稳定" → `skill.debug`
- "帮我补一组单元测试" → `skill.test_implementation`, "升级迁移方案" → `skill.migration`
- "事故分析" → `skill.incident`, "摸清楚现状" → `skill.explore`

Three historical routing bugs confirmed fixed:
1. "生成测试报告" no longer routes to `test_design`
2. "Playwright e2e CI 不稳定" no longer routes to `test_design`
3. "migration + Spring" no longer merges `pack.spring_review`

---

## v1.0.0

### Overview
First complete architecture release of the modular AI engineering assistant repository.

This release establishes the repository as a structured system rather than a loose prompt collection.

---

### Added

#### Core architecture
- `CLAUDE.md` kernel principles
- workflow engine stages:
  - discover
  - evidence
  - context
  - reasoning
  - planning
  - execution
  - verification
  - delivery
- runtime layer:
  - router
  - runtime contract
  - conflict resolution
- behavior layer:
  - review
  - debug
  - refactor
  - optimize
  - document
  - explain
- domain layer:
  - java
  - spring
  - spring-ai
  - playwright
  - mysql
  - redis
  - testing
- template layer:
  - default
  - review report
  - debug report
  - refactor plan
  - implementation plan
  - explanation
  - test plan
  - test report
- checklist layer:
  - general quality
  - review
  - debug
  - refactor
  - verification
  - delivery
- report layer:
  - task report
  - incident report
  - review summary

#### Governance and standards
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- standards for:
  - module authoring
  - naming
  - versioning
  - change policy
  - architecture guardrails

#### Adoption and onboarding
- `README.md`
- `GETTING-STARTED.md`
- `EXAMPLES.md`

#### Integration guides
- Claude Code integration
- Cursor integration
- OpenAI Agents integration

#### Machine-readable layer
- registries for:
  - modules
  - behaviors
  - domains
  - templates
  - checklists
  - reports
  - workflows
  - compositions
  - packs
  - template outputs

#### Schema layer
- schemas for:
  - modules registry
  - workflows registry
  - compositions registry
  - runtime state
  - packs
  - template outputs:
    - default
    - review report
    - debug report
    - refactor plan
    - implementation plan
    - explanation
    - test plan
    - test report

#### Validation and CI
- scripts for:
  - registry schema validation
  - module path checking
  - cross-reference checking
  - pack validation
  - pack reference checking
- GitHub Actions workflow for repository metadata validation

#### Pack layer
- Spring review pack
- Playwright debug pack
- Redis incident pack
- Java refactor pack

---

### Changed

#### Architectural refinement
- separated `runtime` concerns from `engine`
- reduced routing pressure by adding activation signals to behaviors and domains
- clarified templates vs reports boundary
- clarified domain modules as heuristic guides rather than encyclopedic references

#### Registry alignment
- aligned registry naming with `workflow.*` ids
- aligned module registry with runtime layer
- aligned behavior and domain metadata with activation signal model

---

### Notes

This release marks the repository as **architecture complete** for its first full version.

The system is intended to be:
- usable immediately
- maintainable over time
- extendable with tooling
- stable enough for team adoption

Future work is expected to focus more on:
- tooling
- automation
- runtime implementation
- output validation
rather than large architectural redesign.
