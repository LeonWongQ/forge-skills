---
name: optimize
description: >-
  Optimize performance, efficiency, scalability, latency, throughput, memory
  usage, or resource utilization with measurement-driven analysis, bottleneck
  identification, and verified improvement planning.
  Use when the user says: optimize this, make this faster, improve performance,
  speed this up, reduce memory, reduce latency, scale this, performance analysis,
  profiling, this is slow, bottleneck, 优化, 性能优化, 加速, 太慢了, 内存优化.
  For any performance or efficiency improvement request.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
---

# Optimize

## 1. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Identify the optimization target: what needs to be faster, leaner, or more scalable
3. Establish baseline: current performance characteristics (measurements, not guesses)
4. Detect technical domains from the target:
   - Java code → `.claude/forge/domains/java.md`
   - Spring / database → `.claude/forge/domains/spring.md`, `.claude/forge/domains/mysql.md`
   - Cache → `.claude/forge/domains/redis.md`
   - If no domain matches, skip domain loading. Proceed with behavior + template + checklists only.
5. Compose forge modules per section 2
6. Execute: measure → analyze → plan → verify
7. Deliver structured optimization plan

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.claude/forge/behaviors/optimize.md` | Primary: performance, efficiency, scalability improvement |
| Domains | Detected from target | Technology-specific optimization heuristics |
| Template | `.claude/forge/templates/implementation-plan.md` | Output: objective → approach → steps → risks → validation |
| Checklists | `.claude/forge/checklists/general-quality.md` | Baseline quality |
| | `.claude/forge/checklists/verification-checklist.md` | Performance claims must be justified |
| | `.claude/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.full_default` | Full: discover → evidence → context → reasoning → planning → execution → verification → delivery |

## 3. Core Discipline (from optimize.md)

### Optimization Mindset
- **Measure first, optimize second**. Never optimize without baseline data.
- **Identify the bottleneck**. Where is time/memory actually spent? Profiling > guessing.
- **One change at a time**. Change one thing, measure, compare. Otherwise you cannot attribute improvement.
- **Correctness before speed**. A fast wrong answer is worse than a slow correct one.
- **Know when to stop**. Diminishing returns. Set a target, hit it, stop.

### Optimization Dimensions
Identify which dimension matters:
- **Latency**: response time for a single operation (p50, p95, p99)
- **Throughput**: operations per second under load
- **Memory**: heap usage, GC behavior, object allocation
- **Resource utilization**: connections, threads, file handles
- **Scalability**: behavior as load/data volume increases

### Analysis Pattern
1. **Measure baseline**: concrete numbers, not impressions. What is the current state?
2. **Profile**: where is time/memory going? Hot paths, allocation rates, wait times.
3. **Identify bottleneck**: what is the constraint? CPU, I/O, lock contention, network, database, cache miss?
4. **Propose change**: what to change, expected improvement, risk of regression.
5. **Verify**: measure after change. Did it improve? Did anything break?

### Common Pitfalls
- Optimizing code that isn't the bottleneck
- Trading readability for negligible performance gain
- Adding caching without measuring cache hit rate
- Optimizing for a scenario that never occurs in production
- Changing algorithm without understanding data characteristics

## 4. Output Structure

```
## Objective
<what to optimize, target metric, success criterion>

## Baseline Measurements
<current performance data with concrete numbers>

## Bottleneck Analysis
<where time/memory is spent, root cause of inefficiency>

## Proposed Changes
1. <change>: what, expected improvement, risk, verification
2. ...

## Risks
<regression risks, correctness risks, operational risks>

## Validation Plan
<how to measure improvement, what tests to run, acceptance criteria>
```

## 5. Guard

Before delivering:
- [ ] Baseline measurements exist (concrete numbers, not guesses)
- [ ] Bottleneck identified with evidence (profiling, not intuition)
- [ ] Each proposed change has expected improvement stated
- [ ] Correctness risk assessed for each change
- [ ] Validation plan includes before/after measurement
- [ ] Not optimizing non-bottleneck code

## Vue Version Boundary

For a Vue target, read [the shared Vue version-routing contract](.claude/forge/references/vue-version-routing.md) before loading framework guidance. Keep the current task Skill in control; version-specific Vue Skills do not take ownership of review, debugging, refactoring, optimization, or testing intents.
