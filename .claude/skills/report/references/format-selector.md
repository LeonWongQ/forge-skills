# Report Format Selector

## Decision Tree

```
User wants a report
  ├─ Is it about TEST RESULTS?
  │   └─ → Test Report (.claude/forge/templates/test-report.md + .claude/forge/reports/task-report.md)
  │
  ├─ Is it about a PRODUCTION INCIDENT / OUTAGE?
  │   └─ → Incident Report (.claude/forge/reports/incident-report.md + debug behavior)
  │
  ├─ Is it about a CODE/DESIGN REVIEW?
  │   └─ → Review Summary (.claude/forge/reports/review-summary.md + review behavior)
  │
  ├─ Is it about GENERAL TASK COMPLETION / ANALYSIS?
  │   └─ → Task Report (.claude/forge/reports/task-report.md)
  │
  └─ Is it UNCLEAR?
      └─ Ask: "What type of report: test results, incident/postmortem, review summary, or general task report?"
```

## Format Quick Reference

| Report Type | Template | Report Artifact | Key Sections |
|------------|----------|-----------------|--------------|
| Test Report | `.claude/forge/templates/test-report.md` | `.claude/forge/reports/task-report.md` | Execution summary, defects, coverage, risk, release recommendation |
| Incident Report | — | `.claude/forge/reports/incident-report.md` | Timeline, impact, root cause, resolution, prevention, action items |
| Review Summary | — | `.claude/forge/reports/review-summary.md` | Scope, key findings, overall assessment, action items |
| Task Report | — | `.claude/forge/reports/task-report.md` | Objective, findings, conclusions, recommendations |

## Checklist Selection by Report Type

| Report Type | Checklists |
|------------|------------|
| Test Report | general-quality, test-report-checklist, delivery-checklist |
| Incident Report | general-quality, verification-checklist, delivery-checklist |
| Review Summary | general-quality, review-checklist, delivery-checklist |
| Task Report | general-quality, delivery-checklist |

## Key Distinguishing Signals

| Signal | Report Type |
|--------|------------|
| "test results", "测试结果", "test execution", "pass/fail" | Test Report |
| "incident", "outage", "postmortem", "事故", "宕机", "复盘" | Incident Report |
| "review summary", "PR summary", "评审总结" | Review Summary |
| "task report", "summary", "findings", "conclusion" | Task Report |
