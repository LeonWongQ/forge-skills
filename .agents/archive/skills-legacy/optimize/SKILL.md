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
context: fork
---

# Optimize

## 1. Activation Sequence

1. Load forge kernel: `.Codex/forge/AGENTS.md`, `.Codex/forge/AUTOLOAD.md`
2. Identify the optimization target: what needs to be faster, leaner, or more scalable
3. Establish baseline: current performance characteristics (measurements, not guesses)
4. Detect technical domains from the target:
   - Java code → `.Codex/forge/domains/java.md`
   - Spring / database → `.Codex/forge/domains/spring.md`, `.Codex/forge/domains/mysql.md`
   - Cache → `.Codex/forge/domains/redis.md`
   - If no domain matches, skip domain loading. Proceed with behavior + template + checklists only.
5. Compose forge modules per section 2
6. Execute: measure → analyze → plan → verify
7. Deliver structured optimization plan

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.Codex/forge/behaviors/optimize.md` | Primary: performance, efficiency, scalability improvement |
| Domains | Detected from target | Technology-specific optimization heuristics |
| Template | `.Codex/forge/templates/implementation-plan.md` | Output: objective → approach → steps → risks → validation |
| Checklists | `.Codex/forge/checklists/general-quality.md` | Baseline quality |
| | `.Codex/forge/checklists/verification-checklist.md` | Performance claims must be justified |
| | `.Codex/forge/checklists/delivery-checklist.md` | Usable output |
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

## Vue Version Integration

For Vue-related targets, identify the **target package** and verify its resolved `vue` version from its lockfile or installed dependency metadata before loading framework guidance. `package.json` is provisional when no resolved version is available; `.vue`, Vite, Composition API, `<script setup>`, Router, and `import.meta.env` are not version proof.

- Vue `2.0–2.6` → load `domain.vue2`; inspect compiler parity and, for vmd-ui, the resolved package version plus existing imports, registration, and CSS/theme usage.
- Vue `2.7.x` → load `domain.vue2_7`; verify the actual compiler and Vite-compatible plugin/toolchain before applying Vite advice.
- Vue `3.x` → load `domain.vue3_vite`.
- Missing or conflicting evidence → retain the current intent workflow and request the target package/version; do not mix version-specific lifecycle, reactivity, compiler, or build guidance.

`page-test` remains Playwright E2E-only, while component/unit testing remains with `test-implementation`.
