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
---

# Incident

## Route

Use this Skill for production impact or active operational risk. Use `debug` for a non-production defect and `error-analysis` when the primary task is interpreting supplied logs without incident coordination.

Load the debug behavior, incident report template, operational and relevant technical domains, and general/debug/verification/delivery checklists. Read [references/incident-method.md](references/incident-method.md) for active response or postmortem details.

## Active Incident Priorities

Protect users and stabilize service before pursuing a complete root cause. Establish impact, affected scope, start time, current state, severity, and ownership. Preserve evidence while considering mitigations that are reversible and observable.

Maintain a UTC timeline that separates observed facts, actions, and hypotheses. Rank hypotheses by evidence and test them with the lowest-risk discriminating check. Do not turn temporal correlation into causation.

For every mitigation state expected effect, risk, rollback, verification signal, and decision owner. Never recommend destructive production action without explicit authority and resolved targets.

## Root Cause and Follow-Up

Root cause must include trigger, mechanism, and enabling condition. Distinguish root cause from detection gap, response gap, and contributing factors. Action items must address recurrence or detection, have an owner and completion condition, and avoid blame-oriented language.

## Delivery

For an active incident, lead with current status, impact, timeline, evidence, ranked hypotheses, mitigation options, and next decision. For a postmortem, provide summary, impact, timeline, root cause, resolution, contributing factors, lessons, and owned actions.

State what remains unknown and when the next update is expected. Do not declare recovery from one healthy sample; use an observation window proportional to the failure mode.
