---
name: architecture-design
description: >-
  Design system architecture, component topology, API contracts, data models,
  integration patterns, and technical decision frameworks with structured
  tradeoff analysis, ADR-style decision records, and implementation guidance.
  Use when the user says: design the architecture, system design, design this system,
  architecture review, component design, how should I structure this,
  design the API, data model design, database schema design,
  microservice design, integration design, tech stack evaluation,
  architectural decision, design the components, how to split this,
  架构设计, 系统设计, 技术方案, 组件设计, API设计, 数据库设计,
  技术选型, 怎么拆分, 架构评审, 接口设计, 如何设计架构.
  For any system, component, API, or data model design request that requires
  structured architectural thinking with explicit tradeoff analysis.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch, Write]
---

# Architecture Design

## Route

Classify the request as system/component topology, API design, integration design, broad data architecture, or technology selection. Use `data-design` for detailed schemas/indexes, `contract-compatibility` for compatibility assessment, and `plan` when the architecture is already decided and sequencing is the primary need.

Inspect current constraints and evidence before proposing a target. Load only domains confirmed by the target stack. Read [references/architecture-guide.md](references/architecture-guide.md) for the selected design focus.

## Decision Discipline

Every recommendation must connect requirements and constraints to alternatives and tradeoffs. Define measurable quality attributes such as latency, throughput, availability, consistency, security, operability, delivery speed, and cost. Do not recommend a technology or service split without the failure, ownership, and operational model it introduces.

Prefer the simplest design that meets current requirements and has an explicit evolution path. Separate confirmed requirements from assumptions, and identify decisions that are reversible versus expensive to reverse.

## Required Coverage

For a system design, cover boundaries, responsibilities, data ownership, synchronous/asynchronous interactions, failure behavior, trust boundaries, observability, deployment, and evolution. For APIs, cover resources/operations, schemas, errors, pagination, idempotency, auth, versioning, and compatibility. For integrations, cover delivery semantics, retries, ordering, deduplication, timeout, and reconciliation.

Record major decisions in compact ADR form: context, options, decision, rationale, consequences, and validation condition.

## Delivery

Lead with context and constraints, compare credible alternatives, then present the recommended topology/contracts, key decisions, risks, rollout path, and open questions. Use diagrams only when relationships are easier to understand visually.

Default to inline output. Write a design artifact only with an authorized path. Before delivery confirm that alternatives were evaluated fairly, operational costs are visible, interfaces are concrete, and estimates are not presented as measurements.
