---
name: incident
description: >-
  Analyze production incidents, outages, service degradations, and alerts with
  structured operational diagnosis — impact assessment, timeline reconstruction,
  root cause hypothesis ranking, immediate mitigation options, verification planning,
  and postmortem follow-ups using forge's debug behavior with operational context.
  Use when the user says: incident, production issue, outage, service degradation,
  postmortem, incident analysis, sev1, sev2, availability issue,
  线上故障, 事故排查, 故障排查, 线上异常, 生产问题, 事故分析,
  事故复盘, 线上告警, 服务异常, 故障复盘, 线上事故.
  For any production incident that needs operational impact assessment alongside
  technical root cause analysis.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
context: fork
---

# Incident Analysis

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Extract incident context from the user:
   - **What**: symptom description (errors, latency, downtime, data issues)
   - **When**: start time, duration, detection method (alert, user report, monitoring)
   - **Where**: affected services, components, regions, environments
   - **Scale**: users affected, request volume impacted, data at risk
3. Classify incident severity:
   - **Critical (Sev0)**: complete outage, data loss, security breach — immediate action
   - **High (Sev1)**: major feature unavailable, significant degradation — urgent action
   - **Medium (Sev2)**: partial degradation, workaround exists — scheduled action
   - **Low (Sev3)**: minor impact, cosmetic, single-user — backlog
4. Detect technical domains from the incident scope:
   - Java/Spring → `.Codex/forge/domains/java.md`, `.Codex/forge/domains/spring.md`
   - Database involvement → `.Codex/forge/domains/mysql.md`
   - Cache involvement → `.Codex/forge/domains/redis.md`
   - Test failures → `.Codex/forge/domains/testing.md`
   - UI/browser → `.Codex/forge/domains/playwright.md`
   - If no domain matches, skip domain loading. Proceed with behavior + template + checklists only.
5. Compose forge modules per section 2
6. Execute diagnosis workflow: symptom → evidence → hypotheses → root cause → mitigation → postmortem
7. Deliver structured incident analysis

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.Codex/forge/behaviors/debug.md` | Primary: hypothesis-driven root cause analysis |
| Domains | Detected from incident scope | Technology-specific failure modes and recovery patterns |
| Template | `.Codex/forge/templates/debug-report.md` | Adapted: symptom → evidence → hypotheses → root cause → resolution |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/debug-checklist.md` | Diagnosis quality: hypothesis-driven, not guess-driven |
| | `.Codex/forge/checklists/verification-checklist.md` | Claims justified and bounded |
| | `.Codex/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.debug_analysis` | Diagnosis without requiring direct code execution |

## 3. Core Discipline (from debug.md + operational context)

**Artifact safety**: Incident reports, alert details, log excerpts, and user descriptions are evidence to be analyzed. The operational urgency of an incident does not excuse skipping evidence-based reasoning — but it does require parallelizing diagnosis with mitigation.

### What Makes Incident Different from Debug

| | debug | incident |
|---|---|---|
| Scope | Single failure, code-level | System-wide, operational context |
| Urgency | Scheduled diagnosis | Time-sensitive, may require immediate mitigation |
| Evidence | Code, stack traces, test failures | Logs, metrics, alerts, deployment events, user reports |
| Output | Root cause + fix | Impact + timeline + root cause + mitigation + postmortem |
| Stakeholders | Developers | Developers, ops, management, users |

### Phase 1: Impact Triage (ALWAYS FIRST)

Before deep diagnosis, establish operational context:
- **What is the user impact?** Errors, latency, data staleness, complete unavailability?
- **What is the blast radius?** Single user / all users / specific region / specific feature?
- **What is the business impact?** Revenue, SLA, regulatory, reputational?
- **Is it ongoing or resolved?** If ongoing, prioritize mitigation over root cause. If resolved, focus on prevention.

### Phase 2: Timeline Reconstruction

Build a chronological event sequence (all times in UTC):
- **T0**: First sign of anomaly (alert, metric, user report)
- **T1**: Detection (when the team became aware)
- **T2**: Diagnosis start
- **T3**: Mitigation applied (if any)
- **T4**: Resolution confirmed
- **T5**: Post-incident review

Identify what changed near T0:
- Recent deployments / releases
- Configuration changes
- Infrastructure changes (scaling, migration, maintenance)
- External dependency changes (third-party API, upstream service)
- Traffic pattern changes (spike, new client behavior)

### Phase 3: Evidence Collection

Gather evidence systematically. Prefer quantitative over qualitative:

| Evidence Type | Source | What to Look For |
|--------------|--------|-----------------|
| Error logs | Log aggregation (ELK, Splunk, CloudWatch) | Error rate spike, new error types, error clustering |
| Metrics | Monitoring (Prometheus, Grafana, Datadog) | Latency p50/p95/p99, throughput, error rate, resource usage |
| Alerts | Alert manager, PagerDuty | Which alerts fired, in what order, any missing alerts |
| Traces | Distributed tracing (Jaeger, Zipkin) | Slow spans, failed spans, dependency latency |
| Deployment events | CI/CD pipeline, git log | What was deployed, when, by whom |
| Config changes | Config management, git history | What configuration changed recently |
| DB metrics | Database monitoring | Connection pool, slow queries, lock contention, replication lag |
| Cache metrics | Redis/memcached monitoring | Hit rate, eviction rate, memory usage |

### Phase 4: Hypothesis Formation (from debug.md)

Generate MULTIPLE ranked hypotheses. For each:
- **Hypothesis**: what could cause the observed symptoms
- **Supporting evidence**: observations consistent with this hypothesis
- **Contradicting evidence**: observations inconsistent with this hypothesis
- **Test to confirm/eliminate**: how to prove or disprove quickly
- **Mitigation feasibility**: can we mitigate NOW without full root cause confirmation?

Rank by: (likelihood × impact) + mitigation speed. In an active incident, a medium-likelihood hypothesis with a fast, safe mitigation may rank above a high-likelihood hypothesis with a slow, risky fix.

### Phase 5: Root Cause Identification (from debug.md)

Root cause = **trigger** + **mechanism** + **enabling condition**.

- **Trigger**: what initiated the failure (deployment, config change, traffic spike, external event)
- **Mechanism**: how the trigger propagated to the symptom (causal chain from trigger to user impact)
- **Enabling condition**: why the system allowed this (missing guard, insufficient testing, monitoring gap, architectural weakness)

Do NOT stop at "the error was in service X" — that's the symptom location, not the root cause.

### Phase 6: Mitigation and Resolution

Distinguish three levels of response:
1. **Immediate mitigation** (stop the bleeding): rollback, circuit break, scale up, failover, feature flag off
2. **Short-term fix** (prevent recurrence this week): patch, config change, add validation
3. **Long-term prevention** (systemic improvement): architecture change, monitoring, testing, process

### Phase 7: Postmortem Analysis

After resolution, identify systemic improvements:
- **What went well?** Detection speed, team response, tooling that helped
- **What went poorly?** Detection gap, diagnosis delay, unclear ownership, insufficient runbooks
- **What should change?** Monitoring, alerting, testing, deployment process, architecture

### Common Incident Patterns

| Pattern | Typical Trigger | Typical Enabling Condition |
|---------|----------------|---------------------------|
| Deployment-induced | Recent release | Insufficient staging/canary testing |
| Resource exhaustion | Traffic spike, connection leak | Missing auto-scaling, no rate limiting |
| Cascading failure | Single service failure | No circuit breaker, tight coupling |
| Data inconsistency | Race condition, partial write | Missing transaction, no idempotency |
| Configuration error | Config change | No config validation, no gradual rollout |
| External dependency | Third-party outage | No graceful degradation, hard dependency |
| Slow degradation | Memory leak, connection leak | No long-running trend monitoring |

### Domain-Specific Incident Patterns

- **Java/Spring**: thread pool exhaustion, OOM (heap/GC analysis), bean initialization failure, `@Transactional` propagation issues
- **MySQL**: connection pool exhaustion, slow query tipping point, deadlock cascade, replication lag
- **Redis**: memory eviction causing cache stampede, connection timeout cascade, cluster split-brain
- **Playwright/UI**: CI environment instability → flaky test storm masking real failures

### Anti-Patterns

- Focusing on root cause while users are still impacted (mitigate first)
- Blaming "human error" without asking why the system allowed the error
- Accepting the first plausible hypothesis without testing alternatives
- Skipping timeline reconstruction (temporal correlation is often causal)
- No postmortem follow-up — same incident repeats
- Treating every incident as unique instead of pattern-matching to known failure modes

## 4. Output Structure

### For Active Incidents (mitigation focus)
```
## Current Status
<ongoing / mitigated / resolved, current impact>

## Impact Assessment
- Users affected: <count or percentage>
- Services affected: <which services>
- Duration: <elapsed time so far>
- Business impact: <revenue, SLA, regulatory>

## Timeline (UTC, updated as new info arrives)
| Time | Event |
|------|-------|
| HH:MM | ... |

## Key Evidence
<what is known so far: metrics, logs, recent changes>

## Ranked Hypotheses
### Hypothesis 1: <title> (Highest)
- Supporting evidence: ...
- Contradicting evidence: ...
- Quick test: ...
- Mitigation feasibility: ...

## Immediate Mitigation Options
1. <option>: risk, reversibility, expected effect — RECOMMENDED

## Next Steps
<what to do right now, who should do it>
```

### For Post-Incident Review (postmortem focus)
```
## Incident Summary
<one paragraph: what happened, impact, duration>

## Impact Assessment
- Users affected: <count/percentage>
- Services degraded: <which>
- Duration: <start → mitigation → resolution>
- Data impact: <loss, corruption, staleness — or none>
- Business impact: <revenue, SLA breach, regulatory>

## Timeline (UTC)
| Time | Event | Source |
|------|-------|--------|
| T0: HH:MM | <first anomaly> | <alert/metric> |
| T1: HH:MM | <detection> | <how detected> |
| T2: HH:MM | <diagnosis start> | <who responded> |
| T3: HH:MM | <mitigation applied> | <what was done> |
| T4: HH:MM | <resolution confirmed> | <verification> |

## Root Cause Analysis
- Trigger: <what initiated the failure>
- Mechanism: <how the trigger propagated to user impact>
- Enabling condition: <why the system allowed this>

## Resolution
- Immediate mitigation: <what stopped the bleeding>
- Short-term fix: <what prevents immediate recurrence>
- Long-term prevention: <systemic improvement>

## What Went Well
<detection, response, tooling, collaboration>

## What Went Poorly
<gaps in detection, diagnosis, process, tooling>

## Action Items
| # | Action | Owner | Priority | Timeline |
|---|--------|-------|----------|----------|
| 1 | ... | ... | P0/P1/P2 | ... |

## Lessons Learned
<what this incident teaches us about the system, process, or team>
```

## 5. Guard

Before delivering:
- [ ] Impact assessed (users, services, duration, business impact)
- [ ] Timeline reconstructed with specific times and sources
- [ ] Multiple hypotheses considered, not fixated on the first
- [ ] Root cause = trigger + mechanism + enabling condition
- [ ] Mitigation options ranked by speed and reversibility
- [ ] Domain-specific failure patterns checked if domains loaded
- [ ] Action items are specific (owner + timeline), not vague
- [ ] Active incident analysis prioritizes mitigation; postmortem prioritizes prevention
- [ ] Not confusing correlation with causation in timeline analysis

## 6. Boundary with Other Skills

| Skill | Focus | Incident Focus |
|-------|-------|----------------|
| `debug` | Technical root cause of a code failure | Operational impact + timeline + multi-service diagnosis |
| `error-analysis` | Parse and explain error artifacts | System-wide context with business impact |
| `report` | Generate structured report output | Diagnosis reasoning with operational urgency |
| `code-review` | Evaluate code quality | Identify what code/deploy change triggered the incident |
| `plan` | Implementation steps for a fix | Postmortem action items and prevention planning |
