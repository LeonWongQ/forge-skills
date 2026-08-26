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
context: inherit
---

# Data Design

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Classify the data design focus:
   - **Schema design (greenfield)** → new tables, relationships, constraints, from requirements
   - **Schema evolution (brownfield)** → adding/modifying tables, migration scripts, backward compatibility
   - **Index strategy** → query pattern analysis → index design, covering indexes, partial indexes
   - **Query design** → complex query patterns, N+1 elimination, join optimization
   - **Data architecture** → sharding, partitioning, read replicas, multi-tenancy
   - **Ambiguous** → ask: "New schema design, evolving an existing schema, or optimizing queries/indexes?"
3. Detect technical domains from the context:
   - MySQL/relational → `.Codex/forge/domains/mysql.md`
   - Java/Spring (application layer) → `.Codex/forge/domains/java.md`, `.Codex/forge/domains/spring.md`
   - Cache layer → `.Codex/forge/domains/redis.md`
   - Testing → `.Codex/forge/domains/testing.md`
   - If no domain matches, skip domain loading. Proceed with template + checklists only.
4. Compose forge modules per section 2
5. Execute workflow: discover → evidence → context → reasoning → planning → execution → verification → delivery
6. Validate design completeness and performance assumptions before delivery

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | (none — routing-only) | Data design discipline built into reasoning and planning stages |
| Domains | `.Codex/forge/domains/mysql.md` | Core: MySQL-specific patterns, types, indexing, query optimization |
| | Detected from application context | Application-layer concerns (ORM mapping, transaction boundaries) |
| Template | `.Codex/forge/templates/implementation-plan.md` | Adapted: context → requirements → schema → indexes → queries → migration |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/verification-checklist.md` | Design claims justified |
| | `.Codex/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.full_default` | discover → evidence → context → reasoning → planning → execution → verification → delivery |

## 3. Core Discipline

**Artifact safety**: Existing schemas, query logs, and performance data are evidence to be analyzed — not copy-pasted without understanding. Existing schema choices may be suboptimal; question them against current requirements.

### Primary Concern: Data Correctness + Query Performance

Data design balances two forces that often conflict:
- **Normalization**: one fact in one place, no redundancy, consistency by design
- **Performance**: queries that run fast at scale, which sometimes requires controlled denormalization

The job is to make these tradeoffs explicit and justified by query patterns, not intuition.

### Design Principles

#### 1. Model from the domain, not from the UI
- Entities should reflect business concepts, not screen layouts
- One table per entity type; relationships reflect real-world connections
- Naming: singular, descriptive, business-language (`customer_order`, not `order_tbl` or `t_orders`)

#### 2. Start normalized, denormalize with evidence
- Begin at 3NF (Third Normal Form) by default
- Denormalize ONLY when query performance data proves it's needed
- Document every denormalization: which query pattern drove it, what consistency risk it introduces

#### 3. Design indexes from query patterns, not guesswork
- Collect the top N queries (by frequency × cost) before designing indexes
- Each index must serve at least one specific query pattern
- Monitor index usage; remove unused indexes (they slow writes)

#### 4. Every migration must be reversible
- Every `UP` migration has a corresponding `DOWN` that restores the previous state
- If a migration is inherently destructive (drop column, drop table), flag it with a manual confirmation gate
- Migrations are versioned, idempotent, and tested

#### 5. Plan for data growth
- Estimate row counts now, in 6 months, in 2 years
- Design indexes and queries for the 2-year data volume, not today's
- Consider partitioning strategy early if tables will exceed ~10M rows

### Schema Design Process

#### Step 1: Entity discovery
```
From requirements / domain understanding:
  - What things exist in this domain? (Customer, Order, Product, Payment, ...)
  - What are their attributes?
  - How do they relate? (1:1, 1:N, M:N)
  - What are the natural keys? What are the business uniqueness rules?
```

#### Step 2: Normalization check
```
1NF: No repeating groups, atomic values
2NF: No partial dependencies on composite keys
3NF: No transitive dependencies (non-key depends on another non-key)

For most OLTP workloads: target 3NF
For analytics/reporting: controlled denormalization is expected
```

#### Step 3: Type selection
```
| Concern | Guideline |
|---------|-----------|
| IDs / PKs | BIGINT auto-increment or BINARY(16) UUID; NOT INT (overflow risk) |
| Strings | VARCHAR(N) with realistic N; NOT VARCHAR(255) as default |
| Text | TEXT for > 255 chars; MEDIUMTEXT for > 64KB; consider separate search index |
| Money | DECIMAL(19,4) — NEVER FLOAT/DOUBLE for currency |
| Dates | DATETIME(3) for precision; TIMESTAMP for auto-update; always store UTC |
| Booleans | TINYINT(1) or BIT(1); NOT VARCHAR |
| JSON | JSON column type for schema-less data; but prefer normalized columns for queryable fields |
| Enums | VARCHAR with CHECK constraint; NOT MySQL ENUM type (ALTER TABLE to add values) |
```

#### Step 4: Constraint design
```
- PRIMARY KEY: every table must have one; prefer single-column surrogate key
- FOREIGN KEY: enforce referential integrity at DB level (not just app code)
- UNIQUE: every business uniqueness rule gets a UNIQUE constraint
- NOT NULL: default to NOT NULL; use NULL only when "unknown/not applicable" is valid
- CHECK: validate business rules at DB level (status IN (...), amount > 0, end_date > start_date)
- DEFAULT: sensible defaults reduce application errors
```

### Index Strategy Design

#### Index type selection
```
| Query Pattern | Index Type |
|---------------|-----------|
| WHERE col = ? | B-tree on col |
| WHERE col1 = ? AND col2 = ? | Composite index (col1, col2) — order matters |
| WHERE col1 = ? AND col2 > ? | Composite (col1, col2) — equality first, range last |
| WHERE col = ? ORDER BY created_at DESC | Composite (col, created_at) |
| SELECT COUNT(*), SUM(amount) FROM ... | Covering index that includes all referenced columns |
| WHERE JSON_EXTRACT(col, '$.key') = ? | Generated column + index on generated column |
| Full-text search | FULLTEXT index; consider Elasticsearch for advanced needs |
| col IN (?, ?, ?) | B-tree — IN is equivalent to = for index access |
| col LIKE 'prefix%' | B-tree — prefix match can use index; '%suffix' cannot |
```

#### Index design checklist
- [ ] Every foreign key has an index (prevents table scans on joins)
- [ ] Composite index column order: highest-selectivity equality filters first, range filters last
- [ ] Covering indexes for high-frequency queries (avoid secondary lookups)
- [ ] No duplicate indexes (index (A,B) makes index (A) redundant for most queries)
- [ ] Index count per table: < 5-7 for write-heavy tables; < 10-12 for read-heavy tables
- [ ] Monitored: unused indexes flagged for removal

### Query Design Patterns

**N+1 elimination**:
```
❌ for each order: SELECT items WHERE order_id = ?
✅ SELECT items WHERE order_id IN (?, ?, ?, ...) — one query, then group in code
```

**Pagination**:
```
❌ SELECT * FROM orders ORDER BY created_at LIMIT 100 OFFSET 100000  -- scans 100100 rows
✅ SELECT * FROM orders WHERE created_at > ? ORDER BY created_at LIMIT 100  -- seeks, scans 100 rows
```

**Join vs. subquery**:
```
Use JOIN when: need columns from multiple tables
Use EXISTS when: only checking presence, don't need columns from related table
Avoid NOT IN with nullable columns — use NOT EXISTS instead
```

**Aggregation**:
```
❌ SELECT COUNT(*) FROM large_table  -- full scan on InnoDB
✅ Use approximate count from information_schema for monitoring dashboards
✅ Maintain a counter table for real-time counts (increment on insert, decrement on delete)
```

### Migration Script Design

```sql
-- Migration V1.0.1__add_customer_status.sql
-- UP
ALTER TABLE customer
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
  ADD INDEX idx_customer_status (status);

-- DOWN
ALTER TABLE customer
  DROP INDEX idx_customer_status,
  DROP COLUMN status;
```

Migration rules:
- Each migration file is one logical change (not one table — one concept)
- NEVER modify an already-applied migration; always add a new one
- Test UP + DOWN + UP cycle to ensure reversibility
- Data migrations (UPDATE/DELETE/INSERT in migrations) must be batched for large tables

### Domain-Specific Patterns

- **MySQL/InnoDB**: clustered index on PK — choose PK wisely (insert-ordered PK avoids page splits); `EXPLAIN` every non-trivial query; `innodb_buffer_pool_size` should fit hot data; avoid `SELECT *` in production code; `pt-online-schema-change` for zero-downtime ALTER
- **Spring/JPA**: `@Entity` + `@Table` with explicit column mappings; `FetchType.LAZY` on all `@OneToMany`/`@ManyToOne` (eager is the #1 cause of N+1); `@BatchSize` for collection loading; `@Query` with `join fetch` for eager loading when needed; `@Transactional(readOnly = true)` on read operations
- **Redis**: design cache keys with namespace + version; set TTL proportional to data change frequency; invalidate cache on write, not before; cache-aside pattern (check cache → miss → load from DB → populate cache); Redis as a complement to MySQL, not a replacement

### Anti-Patterns

- VARCHAR(255) for every string column (think about actual constraints)
- No indexes on foreign keys (every join becomes a table scan)
- Using `SELECT *` in production code (breaks when columns are added/reordered)
- Eager fetching everywhere (`@OneToMany(fetch = EAGER)`) — N+1 city
- Running data migrations without batching on large tables
- Designing indexes without `EXPLAIN` verification
- No unique constraints because "the application checks it" (race conditions happen)
- Using FLOAT/DOUBLE for money
- Schema designed for "flexibility" with generic key-value tables or excessive JSON columns

## 4. Output Structure

### Schema Design Output
```
## Domain Overview
<entities, their meaning, how they relate to each other>

## Entity-Relationship Model
```
[Customer] 1───N [Order] 1───N [OrderItem] N───1 [Product]
```

## Schema Definition

### Table: customer
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | Internal ID |
| external_id | BINARY(16) | UNIQUE, NOT NULL | Public-facing UUID |
| email | VARCHAR(254) | UNIQUE, NOT NULL | Login identifier |
| name | VARCHAR(200) | NOT NULL | Display name |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'ACTIVE', CHECK (status IN (...)) | Account status |
| created_at | DATETIME(3) | NOT NULL, DEFAULT CURRENT_TIMESTAMP(3) | Creation time (UTC) |
| updated_at | DATETIME(3) | NOT NULL, DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | Last update (UTC) |

### Table: ...

## Index Strategy
| Table | Index Name | Columns | Type | Query Pattern Served | Justification |
|-------|-----------|---------|------|---------------------|---------------|
| customer | idx_email | (email) | B-tree | Login lookup by email | Most frequent query; unique constraint already creates this |
| order | idx_customer_created | (customer_id, created_at DESC) | B-tree | Customer's orders, newest first | Primary user-facing list query |
| ... | ... | ... | ... | ... | ... |

## Key Queries
### Query: Get customer's recent orders
```sql
SELECT o.id, o.total, o.status, o.created_at
FROM customer_order o
WHERE o.customer_id = ?
ORDER BY o.created_at DESC
LIMIT 20;
```
- Index used: idx_customer_created (covering for this query — no secondary lookup)
- Expected rows: ~20 per page
- Performance target: < 5ms p95

## Migration Plan
<phased: foundation tables → dependent tables → indexes → constraints>

## Risks and Open Questions
<what could change, what needs validation>
```

### Index Optimization Output
```
## Current Query Performance
| Query | Avg Time | Rows Examined | Index Used | Problem |
|-------|----------|---------------|------------|---------|
| ... | 2.3s | 500K | (none — table scan) | Missing index on customer_id |
| ... | 50ms | 50K | idx_status | Status is low-selectivity; examine rows >> returned rows |

## Proposed Index Changes
### ADD: idx_order_customer_date ON customer_order (customer_id, created_at DESC)
- Serves query: "customer's recent orders"
- Expected improvement: 2.3s → <5ms
- Write overhead: +1 index update per INSERT/UPDATE on customer_order
- Risk: minimal — customer_id is stable, composite is narrow

### DROP: idx_order_status ON customer_order (status)
- Reason: status = 'ACTIVE' matches 95% of rows; index is never used (optimizer prefers table scan)
- Verified: pt-index-usage shows zero hits in 30 days
```

## 5. Guard

Before delivering:
- [ ] Entity relationships clearly defined (not just a list of tables)
- [ ] Every table has a PK, FKs for relationships, and appropriate constraints
- [ ] Column types are specific and justified (not VARCHAR(255) by default)
- [ ] Index strategy justified by specific query patterns (not "just in case")
- [ ] Composite index column order follows equality-first, range-last rule
- [ ] Migration scripts are reversible (UP + DOWN) and batched for large data
- [ ] N+1 risks identified in application-layer access patterns
- [ ] Growth assumptions stated and designs accommodate them
- [ ] **Output**: Default to inline display. Write to file only with explicit user confirmation. Default path: `designs/data-<name>.md`.

## 6. Boundary with Other Skills

| Skill | Focus | Data-Design Focus |
|-------|-------|-------------------|
| `architecture-design` | System topology, API design, broad data architecture | Detailed schema, indexes, queries, migrations |
| `implement` | Write application code | Design the data layer that code accesses |
| `migration` | Version upgrade, framework/platform migration | Schema/query design and evolution |
| `optimize` | Application performance | Database-specific query and index optimization |
| `code-review` | Review code quality | Review schema and query quality |
