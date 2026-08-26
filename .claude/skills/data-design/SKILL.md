---
name: data-design
description: >-
  Design database schemas, index strategies, query patterns, data integrity
  constraints, migration scripts, and data architecture with domain-driven
  modeling, normalization/denormalization tradeoffs, and performance-aware design.
  Use when the user says: design database schema, design table structure,
  create index strategy, data model design, database design, schema review,
  optimize queries, design data migration, ER diagram, entity design,
  normalize this, denormalize this, database architecture,
  数据库设计, 表结构设计, 索引设计, 数据模型设计, 建表, Schema设计,
  存储方案, 数据架构, 索引优化, SQL优化, 数据迁移方案, ER设计.
  For any database schema, query, index, or data architecture design request.
  Deeper and more database-focused than architecture-design's data model section.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch, Write]
---

# Data Design

## Route

Classify the focus as greenfield schema, schema evolution, index/query optimization, or data architecture. Use `architecture-design` for broader system topology, `migration` for platform/framework upgrades, and `optimize` when database work is only one part of a measured application bottleneck.

Load `.claude/forge/domains/mysql.md` only for confirmed MySQL-compatible targets. Add Java, Spring, Redis, or testing domains only when the application evidence requires them. Read [references/data-design-guide.md](references/data-design-guide.md) for detailed schema, index, query, and migration guidance.

## Core Decisions

Model business facts and invariants before tables. Make ownership, cardinality, lifecycle, natural/business uniqueness, nullability, retention, and consistency boundaries explicit.

Start normalized for transactional data and denormalize only for a named query or operational requirement with a consistency strategy. Design indexes from observed or declared query predicates, ordering, cardinality, and write volume; do not add speculative indexes.

Choose types and constraints that preserve meaning. Money and exact quantities require exact numeric types. Every uniqueness or referential rule that must survive concurrency needs a database-enforced constraint when the target supports it.

## Migration Safety

Prefer reversible, backward-compatible migrations, but do not claim every migration can be losslessly reversed. For destructive or data-transforming changes, define backup/restore evidence, expand-and-contract sequencing, compatibility windows, validation queries, stop conditions, and a forward-fix or recovery plan. Never generate a destructive `DOWN` migration merely to satisfy symmetry.

Do not modify an already-applied migration. Large data changes require batching, progress observability, resumability, and explicit lock/replication impact analysis.

## Deliverable

Provide the domain model, tables and constraints, query patterns, justified indexes, migration/evolution plan, growth assumptions, and risks. For optimization work, show current evidence, proposed change, expected mechanism, write/storage cost, and an `EXPLAIN` or equivalent verification plan.

Default to inline output and write files only with an authorized path. Before delivery confirm that every index serves a query, constraints match business rules, rollback language is honest, and performance claims are labeled as measured or estimated.
