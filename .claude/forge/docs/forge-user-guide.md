# Forge User Guide

Forge is a tool that figures out how to handle your task automatically.

You don't need to memorize which skill to use for which scenario, which template, or which checklist. Just describe what you need, and forge tells you the right way to handle it.

---

## 1. Get Started in One Minute

Once installed, you really only need one command:

```bash
forge ask "what you need"
```

Examples:

```bash
forge ask "review a spring service change for me"
forge ask "analyze a production redis stale-data incident"
forge ask "add unit tests for this module"
forge ask "help me understand the current state of this codebase"
```

It responds with something like:

```
Suggested handling:
- Skill: skill.code_review
- Pack: pack.spring_review
- Behavior: behavior.review
- Workflow: workflow.light_review
- Template: template.review_report
- Domains: domain.java, domain.spring, ...
- Checklists: checklist.general_quality, checklist.review, ...

Why:
- strategy: skill+pack-v6
- confidence: high
- evidence: pack_keyword_any = review
- evidence: pack_keyword_group = spring
```

Now you know: this task should use **code review** mode, paired with the **spring review** pack, output as a **review report**, with quality + review + verification + delivery checklists.

---

## 2. Three Commands, Same Logic

| Command | When to use | Best for |
|---------|-------------|----------|
| `forge ask` | Daily use — describe what you need | Everyone |
| `forge route` | Debug routing — see scores & candidates | Forge developers |
| `forge recommend` | Structured output for programmatic use | Toolchain integration |

All three use the exact same routing logic internally. The only difference is output style.

### `forge ask` — your daily driver

```bash
forge ask "design a test strategy for me"
forge ask "this SQL query is too slow, help me optimize it"
forge ask "explain how spring transaction propagation works"
```

Output reads like a conversation — tells you what to use and why.

### `forge route` — when you want the details

```bash
forge route "design a test strategy for me"
```

Extra output includes:
- Score breakdown (trigger score + keyword bonus)
- All candidate skills ranked
- Which triggers matched

### `forge recommend` — for programmatic use

```bash
forge recommend "design a test strategy for me"
forge --format json recommend "design a test strategy for me"
```

Output is a structured recommendation. JSON mode makes it easy to parse in scripts.

---

## 3. All Commands

### Daily Use

```bash
# Most common: describe what you need, get a recommendation
forge ask "do X for me"

# See routing details
forge route "do X for me"

# Structured recommendation
forge recommend "do X for me"
```

### Advanced

```bash
# Manual assembly: specify skill + pack + template
forge compose --skill explore --pack general_exploration

# Override specific modules
forge compose --skill plan --template implementation_plan --domain java --domain spring
```

### Checking & Maintenance

```bash
# Full health check
forge validate

# Quick check (file paths only)
forge validate --quick

# Health summary
forge doctor

# Export check reports
forge validate --report out/check-report.json
forge doctor --report out/doctor-report.json

# Show version
forge version

# Show overview
forge status
```

### Querying

```bash
# List all skills
forge list skills

# List all packs
forge list packs

# List all templates
forge list templates

# List all domains
forge list domains

# Show details for one item
forge show skill explore
forge show pack spring_review
forge show template default
```

---

## 4. What It Understands

| You say | It routes to | With pack |
|---------|-------------|-----------|
| review a spring service change | code_review | spring_review |
| playwright e2e flaky on CI, help debug | debug | playwright_debug |
| production redis stale-data incident | incident | redis_incident |
| design test strategy | test_design | general_test_plan |
| add unit tests for this module | test_implementation | — |
| spring boot upgrade migration plan | migration | — |
| generate test report and release notes | report | general_test_report |
| help me understand the codebase state | explore | general_exploration |
| refactor this java service | refactor | java_refactor |
| explain spring transaction propagation | explain | — |
| generate API docs for this class | document | — |
| SQL query is slow, help optimize | optimize | — |
| analyze this error log | error_analysis | — |
| how to implement this export feature | plan | — |
| implement a Vue 2 component or vmd-ui feature | vue2 | — |
| implement a Vue 2.7 component or verified Vue 2.7/Vite change | vue2_7 | — |
| implement a Vue 3 component or Vue 3/Vite config | vite_vue3 | — |
| generic Vue/Vite request without version evidence | confirm target package Vue version | — |

**27 skills**: code_review, debug, plan, error_analysis, report, explain, refactor, optimize, document, test_design, incident, test_implementation, migration, explore, page_test, test_strategy, implement, architecture_design, security_review, data_design, dependency_audit, release_readiness, contract_compatibility, auto_compact, vite_vue3, vue2, vue2_7

**9 packs**: spring_review, playwright_debug, redis_incident, java_refactor, general_test_report, general_test_plan, general_exploration, spring_ai_review, release_readiness

---

## 5. Common Use Cases

### Scenario 1: Not sure where to start

```bash
forge ask "help me understand the current state of this module"
```

→ Routes to explore + general_exploration pack. Maps the territory before you commit to a direction.

### Scenario 2: Code Review

```bash
forge ask "review this PR"
forge ask "review a spring service change for me"
```

→ First goes to code_review. Second also matches the spring_review pack automatically.

### Scenario 3: Troubleshooting

```bash
forge ask "this playwright test is flaky on CI, help me debug"
forge ask "analyze this error log"
forge ask "production service is down, incident analysis"
```

→ Routes to debug + playwright_debug, error_analysis, and incident respectively.

### Scenario 4: Testing

```bash
forge ask "design a test strategy"
forge ask "add unit tests for this module"
forge ask "generate test report and release notes"
```

→ Routes to test_design, test_implementation, and report respectively.

### Scenario 5: Planning & Migration

```bash
forge ask "how to implement this export feature"
forge ask "spring boot upgrade migration plan"
forge ask "refactor this java service"
```

→ Routes to plan, migration, and refactor respectively.

---

## 6. Output Formats

### Text mode (default)

All commands output human-readable text by default.

### JSON mode

Add `--format json` to any command:

```bash
forge --format json ask "design a test strategy"
forge --format json route "design a test strategy"
forge --format json recommend "design a test strategy"
forge --format json validate
```

---

## 7. FAQ

### Q: What if the routing result is wrong?

Use `forge route` to see the candidate list and understand why another skill scored higher. Then you can:
- Adjust registry files (add triggers, tune weights)
- Add a regression case to `route-regression.json`

### Q: How do I know forge itself is healthy?

```bash
forge validate
```

All 8 checks passing confirms the current deterministic registry, derived-registry identity, path, reference, pack, semantic, and declared contract-fixture validations. Run the local quality gate for route regression and pytest as well.

### Q: What's the difference between `ask` and `recommend`?

Same internal logic. `ask` outputs conversationally, for humans. `recommend` outputs structurally, for programs. Pick whichever you prefer.

### Q: Can I use only part of forge?

Yes. Forge is modular — packs, domains, and templates you don't use won't affect core functionality.

---

## 8. Quick Reference

```bash
# One-liner entry point
forge ask "..."

# See routing details
forge route "..."

# Structured recommendation
forge recommend "..."

# Manual assembly
forge compose --skill <skill> --pack <pack>

# Full health check
forge validate

# Quick health check
forge validate --quick

# Health summary
forge doctor

# Export reports
forge validate --report out/report.json

# List items
forge list skills
forge list packs
forge list templates
forge list domains

# Show details
forge show skill <name>
forge show pack <name>

# Version
forge version

# Overview
forge status
```
