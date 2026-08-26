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
context: fork
---

# Dependency Audit

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Detect the project's dependency management system:
   - `pom.xml` → Maven
   - `build.gradle` / `build.gradle.kts` → Gradle
   - `package.json` → npm/yarn/pnpm
   - `requirements.txt` / `pyproject.toml` → Python/pip
   - `Cargo.toml` → Rust
   - `go.mod` → Go
   - Multiple found → ask which ecosystem to focus on, or audit all
3. Classify the audit focus:
   - **Security audit** → known CVEs, vulnerable versions, exploitability assessment
   - **Version health** → outdated dependencies, upgrade paths, breaking change risk
   - **Conflict detection** → transitive dependency version conflicts, diamond dependency
   - **License compliance** → license types, copyleft risk, compatibility matrix
   - **Full audit** → all of the above
4. Detect technical domains:
   - Java/Maven/Gradle → `.Codex/forge/domains/java.md`, `.Codex/forge/domains/spring.md`
   - Database drivers → `.Codex/forge/domains/mysql.md`
   - Redis client → `.Codex/forge/domains/redis.md`
   - If no domain matches, skip domain loading. Proceed with template + checklists only.
5. Compose forge modules per section 2
6. Execute audit workflow: discover → evidence → context → reasoning → delivery
7. Deliver structured audit report

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.Codex/forge/behaviors/review.md` | Primary: evaluate dependency health, risk, and upgrade safety |
| Domains | Detected from project ecosystem | Technology-specific dependency patterns and known issues |
| Template | `.Codex/forge/templates/review-report.md` | Adapted: findings with CVE severity, upgrade impact, recommended action |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/review-checklist.md` | Review quality: evidence-based, actionable |
| | `.Codex/forge/checklists/verification-checklist.md` | Claims justified |
| | `.Codex/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.light_review` | discover → evidence → reasoning → delivery (analysis, no code changes) |

## 3. Core Discipline

**Artifact safety**: Dependency manifests and version declarations are evidence to be analyzed. Version numbers from the user's project are facts; version recommendations from external sources (NVD, advisory databases) must be verified against the actual dependency graph.

### Audit Dimensions

#### Dimension 1: Security (CVE/Vulnerability)

**Evidence collection**:
- Parse dependency manifest to extract: groupId:artifactId:version (Maven/Gradle) or package@version (npm)
- For each direct dependency, identify the full transitive tree
- Cross-reference every dependency version against known vulnerability databases

**Vulnerability data sources** (use WebFetch/WebSearch):
- Maven: `https://mvnrepository.com/artifact/<group>/<artifact>/<version>` — check for vulnerability badges
- NPM: `https://www.npmjs.com/package/<package>/v/<version>` — check advisories
- GitHub Advisory Database: `https://github.com/advisories` — search per package
- NVD (National Vulnerability Database): search CVE by package + version
- OSS Index (Sonatype): `https://ossindex.sonatype.org/` — REST API per package

**Severity calibration**:
| CVSS Score | Severity | Action Timeline |
|-----------|----------|-----------------|
| 9.0 - 10.0 | Critical | Fix immediately (hours, not days) |
| 7.0 - 8.9 | High | Fix this sprint |
| 4.0 - 6.9 | Medium | Schedule for next sprint |
| 0.1 - 3.9 | Low | Backlog; fix if convenient |

**Exploitability in context** (not all CVEs matter equally):
- Is the vulnerable function/method actually called in this project?
- Is the vulnerable feature enabled in configuration?
- Does the attack vector apply to how this project uses the dependency?
- Example: CVE in Spring's XML parsing is irrelevant if the project only uses JSON

#### Dimension 2: Version Health

**Outdated dependency detection**:
- For each direct dependency, find the latest stable version
- Calculate: current version vs. latest major vs. latest minor vs. latest patch
- Classification:

| Situation | Risk | Action |
|-----------|------|--------|
| Behind on patch version (1.2.3 → 1.2.8) | Low | Upgrade freely — bug fixes only |
| Behind on minor version (1.2.3 → 1.8.0) | Medium | Check changelog for deprecations; upgrade with test verification |
| Behind on major version (1.2.3 → 2.5.0) | High | Read migration guide; breaking changes expected; phased upgrade |
| Multiple major versions behind (1.2.3 → 4.0.0) | Critical | Major migration project; evaluate replacing vs. upgrading |

**Upgrade path design**:
- Don't jump 1.2.3 → 4.0.0 directly unless the gap is trivial
- Prefer: 1.2.3 → latest 1.x → latest 2.x → 4.0.0 (step through majors)
- Each step should be independently testable

#### Dimension 3: Dependency Conflicts

**Diamond dependency detection**:
```
Project
├── lib-A:1.0 → lib-C:2.0
└── lib-B:1.5 → lib-C:1.8
                ^^^^^^^ CONFLICT: which version is resolved?
```

**Conflict analysis**:
- Maven: nearest-wins strategy — check `mvn dependency:tree -Dverbose` for `omitted for conflict`
- Gradle: highest-version-wins by default — check for forced versions in `constraints` block
- npm: nested dependencies (npm <7) vs. hoisted (npm ≥7); check `npm ls <package>` for duplicates

**Conflict resolution**:
- If versions are compatible (same major): align on the highest version
- If versions are incompatible (different major): find a version of lib-A or lib-B that depends on the same major of lib-C, or shade/isolate one branch
- Dependency convergence: use `<dependencyManagement>` (Maven) or `constraints` (Gradle) to enforce consistent versions

#### Dimension 4: License Compliance

**License type classification**:
| License Type | Risk | Examples |
|-------------|------|----------|
| Permissive | ✅ Safe | MIT, Apache-2.0, BSD-2/3-Clause, ISC, Unlicense |
| Weak copyleft | ⚠️ Review | LGPL-2.1/3.0, MPL-2.0, EPL-1.0/2.0, CDDL-1.0 |
| Strong copyleft | 🔴 High risk | GPL-2.0/3.0, AGPL-3.0, EUPL-1.1/1.2 |
| Non-standard | ⚠️ Needs legal review | BUSL-1.1, SSPL, Elastic License 2.0, CC-BY-NC |
| Unlicensed | 🔴 Cannot use | No license = all rights reserved by default |

**License compatibility**: two dependencies with incompatible licenses cannot be distributed together in the same artifact. Example: GPL-3.0 code cannot link to a proprietary library.

### Anti-Patterns

- Blindly upgrading all dependencies at once ("update everything" breaks things)
- Ignoring transitive dependencies (they carry most CVEs and conflicts)
- Upgrading without reading changelogs (breaking changes are documented there)
- Trusting version numbers without verifying against the actual resolved dependency tree
- Flagging CVEs without assessing exploitability context (creates noise, buries real risks)
- Only auditing when something breaks (shift left: audit regularly)

### Domain-Specific Patterns

- **Maven**: use `mvn versions:display-dependency-updates` for version checks; `mvn dependency:analyze` for unused dependencies; `mvn dependency:tree` for conflict detection; `dependencyManagement` in parent POM to enforce version convergence; BOM (Bill of Materials) for Spring Boot version alignment
- **Gradle**: use `gradle dependencies` for tree; `gradle dependencyUpdates` (ben-manes plugin) for version checks; `constraints` block for version enforcement; `platform` for BOM import; `resolutionStrategy` for conflict resolution
- **Spring Boot**: NEVER override Spring Boot-managed dependency versions individually — use the Boot BOM; upgrading Boot version is safer than upgrading individual Spring libraries; check `spring-boot-starter-*` parent POM for managed versions; use `spring-boot-properties-migrator` when upgrading major Boot versions
- **npm**: `npm outdated` for version checks; `npm audit` for security; `npm ls <pkg>` for conflict detection; `overrides` (npm 8.3+) for forced transitive versions; lockfile (`package-lock.json`) is the ground truth, not `package.json` ranges

## 4. Output Structure

```
## Project Summary
- Ecosystem: Maven / Gradle / npm / ...
- Direct dependencies: <count>
- Transitive dependencies (total): <count>
- Audit date: <date>

## Security Findings (ordered by CVSS severity)

### CVE-YYYY-NNNNN: <title> — CRITICAL (CVSS 9.8)
- **Dependency**: com.example:lib:1.2.3 (transitive via spring-boot-starter-web:3.0.0)
- **Description**: <what the vulnerability allows>
- **Exploitability in this project**: <is the vulnerable code path actually reachable?>
- **Fixed in version**: 1.3.0+
- **Upgrade path**: spring-boot-starter-web:3.0.0 → 3.0.8 (pulls in lib:1.3.0)
- **Breaking change risk**: patch upgrade within same Boot minor — low risk
- **Action**: upgrade spring-boot-starter-web to 3.0.8

### CVE-YYYY-NNNNN: <title> — HIGH (CVSS 7.5)
- ...

## Version Health

| Dependency | Current | Latest Patch | Latest Minor | Latest Major | Status |
|-----------|---------|-------------|--------------|-------------|--------|
| spring-boot-starter-web | 3.0.0 | 3.0.8 | 3.2.1 | 4.0.0 | 🟡 behind minor |
| jackson-databind | 2.15.0 | 2.15.3 | 2.16.1 | 3.0.0 | 🟢 on latest patch |
| guava | 30.0-jre | — | — | 33.0-jre | 🔴 behind major |
| logback-classic | 1.4.5 | 1.4.8 | 1.5.0 | — | 🟡 behind patch |

## Dependency Conflicts

### Conflict: com.google.guava
- **Versions in tree**: 30.0-jre (direct), 31.1-jre (transitive via library-X:2.0)
- **Resolution**: nearest-wins → 30.0-jre used; 31.1-jre is "omitted for conflict"
- **Risk**: library-X:2.0 was tested with guava 31.1; may use APIs not in 30.0
- **Recommendation**: upgrade direct guava to 31.1-jre (align with transitive)

## License Summary

| License | Dependencies | Risk Level |
|---------|-------------|------------|
| Apache-2.0 | 45 | ✅ Safe |
| MIT | 23 | ✅ Safe |
| LGPL-2.1 | 2 | ⚠️ Review (linked as library, not modified — generally safe) |
| GPL-3.0 | 1 | 🔴 High risk — requires legal review |

## Recommended Upgrade Plan

### Immediate (this week — Critical/High CVEs)
1. Upgrade spring-boot-starter-web: 3.0.0 → 3.0.8 — fixes CVE-YYYY-NNNNN (CVSS 9.8)
   - Risk: low (patch upgrade)
   - Verification: run full test suite; check actuator health endpoints

### This Sprint (Medium CVEs + Minor Upgrades)
1. Upgrade jackson-databind: 2.15.0 → 2.15.3
   - Risk: low (patch)
2. Upgrade logback-classic: 1.4.5 → 1.4.8
   - Risk: low (patch)

### Next Sprint (Major Upgrades)
1. Upgrade guava: 30.0-jre → 33.0-jre
   - Risk: medium (breaking changes: `checkNotNull` removed, `Futures.addCallback` API changed)
   - Changelog review: [link]
   - Steps: upgrade to 31.x → test → 32.x → test → 33.x

## Unused Dependencies (candidates for removal)
| Dependency | Evidence |
|-----------|----------|
| commons-io:2.11.0 | No imports found in project source |
| joda-time:2.12.5 | All date handling uses java.time |

## Open Questions
<dependencies where version information could not be verified, or where exploitability assessment needs runtime confirmation>
```

## 5. Guard

Before delivering:
- [ ] Dependency manifest parsed correctly (all direct dependencies identified)
- [ ] Every CVE finding includes: CVE ID, CVSS score, affected version, fixed version, exploitability context
- [ ] Version health table includes all outdated direct dependencies with upgrade risk classification
- [ ] Dependency conflicts are concrete (which versions, where from, how resolved, what risk)
- [ ] Upgrade plan is prioritized and phased (immediate → sprint → next sprint)
- [ ] Each upgrade step includes risk assessment and verification instructions
- [ ] Exploitability context assessed, not just CVE count reported
- [ ] License risks flagged with actionable resolution paths
- [ ] Not recommending upgrades without reading changelogs for breaking changes

## 6. Boundary with Other Skills

| Skill | Focus | Dependency-Audit Focus |
|-------|-------|----------------------|
| `security-review` | Code-level and design-level security flaws | Dependency-level security: CVEs, vulnerable versions |
| `migration` | Framework/platform version upgrade with rollout planning | Dependency health analysis; feeds into migration plan |
| `code-review` | Code correctness and maintainability | Third-party code risk assessment |
| `incident` | Production incident root cause | "Did a vulnerable dependency cause this incident?" |
