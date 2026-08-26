---
name: dependency-audit
description: >-
  Audit project dependencies — analyze dependency trees, detect version conflicts,
  identify known CVE vulnerabilities, check license compliance, find unused or
  outdated dependencies, and recommend safe upgrade paths with impact assessment.
  Use when the user says: dependency audit, check dependencies, scan for vulnerabilities,
  dependency analysis, check for CVEs, outdated dependencies, version conflict,
  dependency tree, license check, audit libraries, upgrade dependencies,
  check security of dependencies, npm audit, maven dependency check, pip audit,
  依赖审计, 依赖检查, 漏洞扫描, 依赖分析, CVE扫描, 依赖冲突, 版本冲突,
  安全依赖检查, 依赖升级, 过期依赖, 许可证合规, 第三方库审计.
  For any project dependency health, security, or upgrade analysis.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls, mvn *, gradle *, npm *, pip *, cargo *), WebFetch, WebSearch]
---

# Dependency Audit

## Route

Identify package managers, manifests, lockfiles, modules, runtime/build/test scopes, and deployment targets before choosing commands. Use `security-review` when dependency risk is one part of a broader threat review and `migration` for an already-selected major upgrade.

Read [references/audit-method.md](references/audit-method.md) for security, version, conflict, license, and unused-dependency analysis. Load language domains only when needed to interpret ecosystem-specific resolution behavior.

## Evidence Rules

Prefer resolved lockfile/tree evidence over manifest ranges. Record tool, database/advisory source, timestamp, ecosystem, resolved version, dependency path, and affected runtime scope. An advisory match is not automatically exploitable; an apparently unused dependency is not removable until dynamic loading, plugins, generated code, and build usage are considered.

Do not run mutation or automatic-fix commands during an audit unless the user requested upgrades. Never claim that absence from one scanner proves absence of vulnerabilities.

## Prioritization

Rank findings by exploitability in this project, affected environment, reachable functionality, severity, fix availability, and operational exposure. Keep vulnerability, version health, license compatibility, conflict, and maintenance status as separate dimensions.

For an upgrade recommendation, state current and target versions, why the target is selected, breaking-change evidence, transitive impact, rollback path, and verification scope. Prefer the smallest supported version that resolves the problem unless broader modernization was requested.

## Delivery

Report project scope and evidence sources, then security findings, version/conflict health, license concerns, unused candidates, and a phased upgrade plan. Clearly label confirmed, likely, and unverified findings.

Before delivery confirm lockfile evidence, dependency paths, runtime relevance, advisory freshness, and that proposed commands preserve user intent.
