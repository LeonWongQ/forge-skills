# Forge Usage Cases

Real-world routing examples — what the user says, how forge routes it, and why.

---

## Case 1: Spring Service Review

**User input:**
> 帮我 review 一个 spring service 改动

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.code_review` |
| Pack | `pack.spring_review` |
| Template | `template.review_report` |
| Domains | domain.java, domain.spring, domain.testing |
| Confidence | high |

**Why this routing:**
- `review` trigger hits `skill.code_review` directly
- `spring` + `service` keywords match `pack.spring_review`'s routing block (`keywords_all_groups: [["spring"], ["review"]]`)
- Pack score_bonus=12 strengthens pack selection evidence; confidence remains controlled by the selected skill route policy
- Spring-specific domains are activated by the pack

**What the user gets:**
A structured review report covering correctness, transaction risk, DI quality, and test confidence — domain-aware and delivered in review_report format.

---

## Case 2: Playwright Flaky Test Debug

**User input:**
> 这个 playwright 用例在 CI 上 flaky，帮我定位下

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.debug` |
| Pack | `pack.playwright_debug` |
| Template | `template.debug_report` |
| Domains | domain.playwright, domain.testing |
| Confidence | high |

**Why this routing:**
- `playwright` + `flaky` + `ci` hit `pack.playwright_debug`'s keyword groups → pack score=14
- `定位` trigger hits `skill.debug` → debug skill active
- `skill.test_design` is penalized by playwright_debug penalty (weight=3) + tie-break rule
- Domains from pack: playwright (locator/wait strategy) + testing (isolation/assertion quality)

**What the user gets:**
A debug report focused on locator quality, wait strategy, test isolation, and CI-specific failure modes — not a test redesign.

---

## Case 3: Redis Incident Analysis

**User input:**
> 帮我分析一个线上 redis 旧数据事故

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.incident` |
| Pack | `pack.redis_incident` |
| Template | `template.debug_report` |
| Domains | domain.redis, domain.java, domain.spring, domain.mysql |
| Confidence | high |

**Why this routing:**
- `redis` + `旧数据` hit `pack.redis_incident`'s keyword groups → pack score_bonus=15
- `线上` + `事故` hit `skill.incident`'s incident keyword_set → incident wins over debug/error_analysis via tie-break
- Domains span redis (cache semantics) + mysql (persistence) + spring (transaction boundary)

**What the user gets:**
An incident analysis with timeline, impact assessment, cache consistency root cause, and mitigation options — focused on stale-read patterns.

---

## Case 4: Test Design

**User input:**
> 帮我设计测试方案

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.test_design` |
| Pack | `pack.general_test_plan` |
| Template | `template.test_plan` |
| Domains | domain.testing |
| Confidence | high |

**Why this routing:**
- `测试方案` trigger hits `skill.test_design` directly
- `测试` + `设计` hit `pack.general_test_plan`'s keyword groups → pack score_bonus=12
- test_design keyword_set provides keyword_bonus weight=5

**What the user gets:**
A structured test plan with scope, strategy, layers, scenarios, risk priorities, entry/exit criteria, and resource estimates.

---

## Case 5: Test Implementation

**User input:**
> 帮我补一组单元测试

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.test_implementation` |
| Confidence | medium |

**Why this routing:**
- `帮我补` trigger hits `skill.test_implementation` (added to fix confidence gap)
- `单元测试` in keyword_set provides bonus weight=7
- tie-break: when test_implementation vs test_design gap ≤ 4, prefer test_implementation
- Confidence=medium because the gap is moderate; adding more specific triggers could push to high

**What the user gets:**
An implementation plan for adding tests — fixture design, mock/stub strategy, scope per layer, and verification approach.

---

## Case 6: Migration Planning

**User input:**
> 给我一个 spring boot 升级迁移方案

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.migration` |
| Template | `template.implementation_plan` |
| Confidence | high |

**Why this routing:**
- `升级` + `迁移方案` hit `skill.migration`'s migration keyword_set → keyword_bonus weight=6
- `pack.spring_review` is strictly filtered: its preferred_skill is `skill.code_review` ≠ `skill.migration`, and it's not in PACK_CROSS_SKILL_ALLOWED
- Migration wins over plan via tie-break (max_gap=4, prefer migration)

**What the user gets:**
A phased migration plan with compatibility assessment, risk evaluation, rollout phasing, rollback strategy, and verification gates.

---

## Case 7: Test Report Generation

**User input:**
> 帮我整理测试报告和发布建议

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.report` |
| Pack | `pack.general_test_report` |
| Template | `template.test_report` |
| Confidence | high |

**Why this routing:**
- `测试报告` + `报告` hit `skill.report`'s report keyword_set → keyword_bonus weight=5
- `test` + `报告` hit `pack.general_test_report`'s keyword groups → pack score_bonus=10
- `skill.test_design` is penalized by report penalty (weight=3) + report vs test_design tie-break

**What the user gets:**
A structured test report summarizing execution results, defects, coverage, risks, and release recommendations.

---

## Case 8: Exploration / Scoping

**User input:**
> 先帮我摸清楚这个模块现状

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.explore` |
| Pack | `pack.general_exploration` |
| Template | `template.exploration` |
| Confidence | high |

**Why this routing:**
- `先摸清楚` trigger hits `skill.explore` directly
- `先` + `摸清楚` hit `pack.general_exploration`'s keyword groups → pack score_bonus=10
- `skill.plan` is penalized by explore penalty (weight=2) + explore vs plan tie-break
- No behavior assigned — exploration intentionally avoids committing to a thinking mode

**What the user gets:**
A scannable exploration output: current understanding → landscape → observations → possible directions → recommended next step. Lightweight, not over-formalized.

---

## Case 9: Java Refactor

**User input:**
> 帮我重构这个 java service

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.refactor` |
| Pack | `pack.java_refactor` |
| Template | `template.refactor_plan` |
| Domains | domain.java, domain.spring, domain.mysql |
| Confidence | high |

**Why this routing:**
- `重构` trigger hits `skill.refactor` directly
- `java` + `重构` hit `pack.java_refactor`'s keyword groups → pack score_bonus=12
- `skill.migration` is penalized by migration penalty on refactor

**What the user gets:**
A behavior-preserving refactor plan — structural improvements sequenced by risk, with verification gates at each step.

---

## Case 10: Concept Explanation

**User input:**
> 解释一下 spring 事务传播机制

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.explain` |
| Template | `template.explanation` |
| Workflow | `workflow.light_explanation` |
| Confidence | high |

**Why this routing:**
- `解释` trigger hits `skill.explain` directly
- Light explanation workflow — no heavy evidence/verification stages needed
- Domains loaded from context (spring transaction → domain.spring)

**What the user gets:**
A progressive-depth explanation: core mechanism → key behaviors → common pitfalls → compare-and-contrast with alternatives.

---

## Case 11: Documentation

**User input:**
> 帮这个类生成文档

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.document` |
| Template | `template.default` |
| Confidence | high |

**Why this routing:**
- `生成文档` trigger hits `skill.document` directly
- Document uses `template.default` — documentation output is content, not a report structure
- Focus on accuracy, clarity, and audience-fit

**What the user gets:**
Audience-focused documentation — class-level API docs, usage context, and key design notes.

---

## Case 12: Performance Optimization

**User input:**
> 这个 SQL 查询太慢了，帮我优化

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.optimize` |
| Template | `template.implementation_plan` |
| Confidence | high |

**Why this routing:**
- `优化` trigger hits `skill.optimize` directly
- `skill.plan` is penalized — optimization is the primary mode
- MySQL domain loaded from context (SQL query → domain.mysql)

**What the user gets:**
A measurement-driven optimization plan — bottleneck identification → root cause → proposed fix → verification approach → expected improvement.

---

## Case 13: Error Log Analysis

**User input:**
> 帮我分析这段报错日志

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.error_analysis` |
| Template | `template.debug_report` |
| Confidence | high |

**Why this routing:**
- `报错日志` keyword hits `skill.error_analysis`'s error_analysis keyword_set → weight=4
- `skill.incident` is penalized — no incident keywords present ("线上/生产/事故")
- Debug behavior + debug_report template for root cause analysis

**What the user gets:**
A structured error analysis — stack trace interpretation, root cause hypothesis, likely remediation, and verification steps.

---

## Case 14: Implementation Planning

**User input:**
> 怎么实现这个导出功能

**Route result:**
| Field | Value |
|-------|-------|
| Skill | `skill.plan` |
| Template | `template.implementation_plan` |
| Confidence | high |

**Why this routing:**
- `实现` in plan keyword_set provides keyword_bonus
- `怎么` + generic plan trigger (lightweight match via generic_trigger_penalties)
- `skill.test_design` is penalized by test_design penalty on plan

**What the user gets:**
An implementation plan — scope, design decisions, implementation sequence, risk points, and verification approach.

---

## Routing Summary

| User says | Skill | Pack | Confidence |
|-----------|-------|------|------------|
| 帮我 review spring service 改动 | code_review | spring_review | high |
| playwright CI flaky 定位 | debug | playwright_debug | high |
| 线上 redis 旧数据事故 | incident | redis_incident | high |
| 帮我设计测试方案 | test_design | general_test_plan | high |
| 帮我补一组单元测试 | test_implementation | — | medium |
| spring boot 升级迁移方案 | migration | — | high |
| 整理测试报告和发布建议 | report | general_test_report | high |
| 先帮我摸清楚模块现状 | explore | general_exploration | high |
| 帮我重构 java service | refactor | java_refactor | high |
| 解释 spring 事务传播机制 | explain | — | high |
| 帮这个类生成文档 | document | — | high |
| SQL 查询太慢帮我优化 | optimize | — | high |
| 分析这段报错日志 | error_analysis | — | high |
| 怎么实现这个导出功能 | plan | — | high |

---

## How to Add New Cases

1. Use a realistic user input — what someone would actually type
2. Run `forge route "<input>"` to see the current routing result
3. If the result is wrong, fix the routing config (triggers, keywords, bias rules, tie-breaks)
4. Add the case to `registry/route-regression.json`
5. Run `python scripts/check-route-regression.py` to verify

The regression file lives at `registry/route-regression.json`. Each case needs:
- `id`: unique identifier, e.g. `route.explain.spring_transaction`
- `mode`: `route` or `recommend`
- `input`: the user's exact words
- `expected`: skill, pack (optional), confidence_min, forbidden_skills/forbidden_packs
- `notes`: what this case validates
