---
name: error-analysis
description: >-
  Analyze errors, stack traces, exception logs, crash dumps, application logs,
  CI failure logs, system error messages, and warning patterns to extract root
  causes, patterns, and remediation strategies.
  Use when the user says: analyze this error, what does this error mean,
  analyze this stack trace, analyze these logs, error analysis, log analysis,
  what does this exception mean, look at this crash, examine this log,
  what went wrong here, parse this error, investigate this exception,
  help me understand this stack trace,
  分析报错, 分析这个错误, 看下这个日志, 这个异常什么意思, 帮我分析下堆栈,
  错误分析, 日志分析, 崩溃分析.
  For any error artifact or log analysis where the user provides the error directly.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), WebFetch, WebSearch]
---

# Error Analysis

## 1. Distinction from Debug

| | debug | error-analysis |
|---|---|---|
| Input | User describes a failure symptom | User provides an error artifact directly |
| Starting point | "Something is wrong, help me find out why" | "Here is the error/log/stack trace — analyze it" |
| Approach | Hypothesis-driven investigation | Artifact-driven parsing and pattern matching |

If the user provides a stack trace, log excerpt, error message, or crash dump as the primary input, use this skill. If they describe a failure without an error artifact, use `debug` instead.

## 2. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Parse the error artifact to identify:
   - Error type (exception class, error code, signal)
   - Error message (the exact text)
   - Location (class, method, file, line number)
   - Causal chain (caused-by chain for nested exceptions)
   - Artifact type: stack trace / log excerpt / crash dump / error code
3. Classify the error layer:
   - **Application code**: your project's classes
   - **Framework**: Spring, Hibernate, etc.
   - **Library**: third-party dependency
   - **Infrastructure**: database, network, filesystem, container
4. Detect technical domains from the error source:
   - JDBC / SQLException → `.claude/forge/domains/mysql.md`
   - Spring / Bean / Transaction → `.claude/forge/domains/spring.md`
   - Redis / Jedis / Lettuce → `.claude/forge/domains/redis.md`
   - JVM / GC / OOM → `.claude/forge/domains/java.md`
   - Test failures, assertion errors → `.claude/forge/domains/testing.md`
   - If no domain matches the error source, skip domain loading. Work with general error analysis patterns only. Note unapplied domains.
5. Compose forge modules per section 3
6. Execute analysis: parse → classify → match patterns → explain → recommend
7. Deliver structured error analysis

## 3. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.claude/forge/behaviors/debug.md` | Debug discipline applied to error artifacts |
| Domains | Detected from error source | Domain-specific failure patterns |
| Template | `.claude/forge/templates/debug-report.md` | Adapted for error artifact analysis |
| Checklists | `.claude/forge/checklists/general-quality.md`, `.claude/forge/checklists/debug-checklist.md`, `.claude/forge/checklists/delivery-checklist.md` | |
| Workflow | `workflow.debug_analysis` | |

## 4. Core Discipline

### Error Artifact Parsing
1. **Error type**: What class of error? (NullPointerException, SQLException, TimeoutException, etc.)
2. **Error message**: What does it say verbatim? Every word matters.
3. **Location**: Exact class, method, file, line. Is it your code or a dependency?
4. **Causal chain**: For nested exceptions, trace from root cause to surface. The outermost exception is often a wrapper — the root cause is deeper.
5. **Context in the artifact**: Timestamps, thread names, request IDs, SQL statements, parameter values — extract all structured data.

### Layer Identification
- **Application layer**: fix is in your control
- **Framework layer**: likely a misuse of framework API or configuration issue
- **Library layer**: version incompatibility, API misuse, known bug
- **Infrastructure layer**: network, database, memory, disk — check operational state

### Pattern Matching
Match the error against known failure patterns for the detected domain. See `.claude/skills/error-analysis/references/error-patterns.md` for domain-specific patterns.

### Explanation (not just description)
- What does this error MEAN in plain language?
- Why did it occur in THIS specific context?
- What is the most likely fix direction?
- Is this a symptom of a deeper problem?

## 5. Output Structure

```
## Error Summary
- Type: <exception class>
- Message: <verbatim>
- Location: <class.method(file:line)>
- Layer: application | framework | library | infrastructure
- Severity: critical | high | medium | low

## Causal Chain
1. Root cause: ...
2. Intermediate: ...
3. Surface: ...

## What This Error Means
<plain-language explanation, 2-3 sentences>

## Why It Occurred
<contextual analysis: what conditions enabled this>

## Fix Direction
<actionable fix with rationale>

## Prevention
<how to prevent this class of error in the future>
```

## 6. Guard

- [ ] Error type, message, and location extracted correctly
- [ ] Layer classified (app / framework / library / infrastructure)
- [ ] Causal chain traced (root → surface, not just surface)
- [ ] Domain-specific patterns checked if domain loaded
- [ ] Fix direction is actionable and explained
- [ ] Not just "this is an X exception" — explained what it means and why
