---
name: test-strategy
description: >-
  Analyze existing test reports, execution results, and defect data to formulate
  testing strategy, design targeted test cases, define auto-assertion rules, and
  diagnose test gaps. Transforms test evidence into actionable testing decisions.
  Use when the user says: analyze test report, review test results, formulate
  test strategy, design test cases from report, what should we test next,
  test gap analysis, create test plan from results, auto-assertion strategy,
  test coverage review, improve test strategy, test optimization plan,
  based on this report, given these test results, from this defect data,
  分析测试报告, 制定测试策略, 根据测试结果制定用例, 测试缺口分析,
  自动化断言策略, 测试优化方案, 基于报告设计测试, 测试策略优化,
  从测试报告看应该加什么测试, 测试覆盖分析, 测试改进方案.
  For any test strategy, test case design, or test optimization driven by
  existing test reports and execution data.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
---

# Test Strategy

## Route

Use this Skill only when existing execution evidence, reports, coverage data, or defects drive the strategy. Use `test-design` for a strategy derived mainly from requirements and `test-implementation` when the user primarily wants test code.

Classify the task as strategy formulation, gap analysis, assertion calibration, or test-health diagnosis. Read [references/strategy-method.md](references/strategy-method.md) for the selected path; do not load unrelated sections by default.

Compose only the required Forge modules: `.forge-skill/forge/domains/testing.md`, `workflow.full_default`, the implementation-plan template, and general quality, verification, and delivery checklists.

## Evidence Discipline

Extract concrete facts before recommending work: pass/fail totals, failure categories, flaky rate, duration, coverage dimensions, escaped defects, affected components, environment, and time window. Separate observed data from inference and state when the input cannot support a conclusion.

Prioritize with risk rather than raw coverage percentage. Consider business impact, change frequency, defect history, technical complexity, observability, and current test strength. Every proposed case must trace to evidence, a declared risk, or an explicit requirement.

## Strategy Contract

For each priority area define:

- target behavior and failure cost;
- appropriate layer: unit, integration, contract, E2E, performance, or security;
- representative, boundary, negative, and known-failure cases as applicable;
- assertion strength and required diagnostic evidence;
- owner or implementation phase when the user needs a roadmap.

Do not compensate for a missing contract assertion with more shallow tests. Do not recommend broad E2E expansion when a lower layer can prove the behavior more cheaply and deterministically.

## Output

Lead with an input summary and prioritized gaps. Then provide the testing strategy, designed cases, assertion calibration, implementation order, and unresolved risks. A case should include priority, target layer, scenario, preconditions, action, expected result, assertion rules, and traceability.

Default to inline output. Write a report only when the user authorizes a path. Before delivery confirm that numbers match the source, gaps are prioritized, assertions are behavior-specific, and recommendations do not exceed the evidence.
