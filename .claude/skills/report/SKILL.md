---
name: report
description: >-
  Generate structured reports including test execution reports, incident
  postmortems, review summaries, task completion reports, and status reports
  using forge's domain-aware templates and quality checklists.
  Use when the user says: create a report, generate a report, test report,
  incident report, write a report, summarize results, create a summary,
  test results report, postmortem, status report, task report,
  generate a test report, write an incident report, create a review summary,
  build a report from these results,
  报告, 测试报告, 事故报告, 总结报告, 写报告, 生成报告, 汇总, 复盘报告.
  For any structured report generation request.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
---

# Report

## 1. Activation Sequence

1. Load forge kernel: `.claude/forge/CLAUDE.md`, `.claude/forge/AUTOLOAD.md`
2. Determine report type from user intent (see section 2)
3. Detect technical domains from report subject:
   - Test results → `.claude/forge/domains/testing.md`
   - Java/Spring service incident → `.claude/forge/domains/java.md`, `.claude/forge/domains/spring.md`
   - Database incident → `.claude/forge/domains/mysql.md`
   - Cache incident → `.claude/forge/domains/redis.md`
   - If no domain matches the report subject, skip domain loading. Proceed with template + checklists only.
4. Compose forge modules per section 3
5. Collect, organize, and summarize the relevant data
6. Generate structured report
7. Validate against report-specific checklist before delivery

## 2. Report Type Selection

| User Intent | Report Type | Forge Template | Forge Report Artifact |
|-------------|------------|----------------|----------------------|
| Test execution results, test summary | Test Report | `.claude/forge/templates/test-report.md` | `.claude/forge/reports/task-report.md` |
| Production incident, outage, postmortem | Incident Report | — | `.claude/forge/reports/incident-report.md` |
| Code/design review summary, PR wrap-up | Review Summary | — | `.claude/forge/reports/review-summary.md` |
| General task completion, analysis findings | Task Report | — | `.claude/forge/reports/task-report.md` |
| Ambiguous | Ask: "What type of report: test results, incident/postmortem, review summary, or general task report?" | | |

See `.claude/skills/report/references/format-selector.md` for detailed selection guide.

## 3. Forge Module Composition

### Test Report
| Module | Path |
|--------|------|
| Template | `.claude/forge/templates/test-report.md` |
| Checklists | `.claude/forge/checklists/general-quality.md`, `.claude/forge/checklists/test-report-checklist.md`, `.claude/forge/checklists/delivery-checklist.md` |
| Report | `.claude/forge/reports/task-report.md` |

### Incident Report
| Module | Path |
|--------|------|
| Behavior | `.claude/forge/behaviors/debug.md` (for root cause analysis) |
| Checklists | `.claude/forge/checklists/general-quality.md`, `.claude/forge/checklists/verification-checklist.md`, `.claude/forge/checklists/delivery-checklist.md` |
| Report | `.claude/forge/reports/incident-report.md` |

### Review Summary
| Module | Path |
|--------|------|
| Behavior | `.claude/forge/behaviors/review.md` |
| Checklists | `.claude/forge/checklists/general-quality.md`, `.claude/forge/checklists/review-checklist.md`, `.claude/forge/checklists/delivery-checklist.md` |
| Report | `.claude/forge/reports/review-summary.md` |

### Always add domains detected from subject.

## 4. Core Discipline

### All Reports
- Lead with the **conclusion or summary** — don't bury it
- Distinguish **facts** (observed, measured) from **assessments** (judged, interpreted)
- Be **specific**: reference exact counts, timestamps, versions, environments
- Include **risks and unknowns** — a report that hides uncertainty is misleading
- Make **recommendations actionable**: who should do what, in what priority

### Test Report Specific
- Execution summary: total / passed / failed / blocked / skipped
- Defect summary: grouped by severity, linked to test cases
- Coverage assessment: what was tested, what was NOT tested
- Risk-based release recommendation: Go / No-Go / Conditional Go

### Incident Report Specific
- Timeline (UTC): detection → diagnosis → mitigation → resolution
- Impact: users affected, duration, data loss, revenue impact
- Root cause: trigger + mechanism + enabling condition (from debug discipline)
- Action items: immediate fixes + preventive measures, each with owner

### Review Summary Specific
- Scope: what was reviewed
- Key findings: top issues found, ordered by severity
- Overall assessment: acceptable / needs changes / blocked
- Action items from review

## 5. Output Structure

### Test Report
```
## Basic Information (project, version, environment, date)
## Execution Summary (total/passed/failed/blocked/skipped)
## Defect Summary (grouped by severity)
## Coverage Assessment
## Risk Assessment
## Release Recommendation
```

### Incident Report
```
## Incident Summary
## Timeline (UTC)
## Impact Assessment
## Root Cause Analysis
## Resolution
## Prevention and Action Items
```

### Review Summary
```
## Scope
## Key Findings
## Overall Assessment
## Action Items
```

## 6. Guard

- [ ] Report type correctly selected
- [ ] Conclusion/summary at the top, not buried
- [ ] Facts separated from assessments
- [ ] Numbers are specific (not "some", "several", "a few")
- [ ] Risks and unknowns disclosed
- [ ] Recommendations are actionable (who, what, priority)
- [ ] **Output**: Default to inline display. Write to file only with explicit user confirmation. Default output path: `reports/<report-name>.md`.
