# Test Report Workflow

## 1. Purpose
This workflow defines how to collect, summarize, review, and publish a test report after a test cycle, test phase, or validation activity.
It aims to provide a clear view of test execution results, defect status, remaining risks, and recommendations.

---

## 2. Inputs
Typical inputs for test reporting include:
- Approved test plan
- Test cases / checklists
- Test execution records
- Defect records
- Re-test / regression results
- Environment information
- Requirement / scope baseline
- Evidence such as screenshots, logs, or system outputs

---

## 3. Workflow Steps

### Step 1: Confirm reporting scope and baseline
Actions:
- Confirm which test cycle, version, or scope the report covers
- Confirm test type and execution period
- Align the report with the original test plan or agreed scope
- Note any scope changes during execution

Outputs:
- Report scope baseline
- Basic information section

Checklist:
- Is the covered version/build clear?
- Is the test period defined?
- Are scope changes recorded?

---

### Step 2: Collect execution data
Actions:
- Gather test case execution results
- Count total, executed, passed, failed, blocked, and not-run cases
- Collect defect counts and status breakdown
- Gather re-test and regression results if applicable

Outputs:
- Execution summary
- Raw result set

Checklist:
- Are counts complete and consistent?
- Are blocked/not-run items explained?
- Are re-test results included where needed?

---

### Step 3: Summarize coverage
Actions:
- Map executed tests back to requirements or scenarios
- Summarize coverage of main flows, alternative flows, exception flows, and edge cases
- Document any gaps or intentionally excluded areas
- Note non-functional coverage if it was part of the scope

Outputs:
- Coverage summary
- Coverage gaps

Checklist:
- Does coverage reflect the agreed scope?
- Are untested areas clearly visible?
- Are important risk areas covered?

---

### Step 4: Summarize defects and issue patterns
Actions:
- Group defects by severity, priority, status, module, or category
- Highlight critical and major defects
- Identify recurring failure patterns
- Summarize any known issue trends or root causes if available

Outputs:
- Defect summary
- Defect analysis

Checklist:
- Are major defects highlighted?
- Is impact described clearly?
- Are recurring issue areas visible?

---

### Step 5: Document risks and limitations
Actions:
- Record unresolved defects
- Record environment, data, dependency, or timing limitations
- Record untested scope or partially tested scenarios
- Document assumptions and confidence level of the result

Outputs:
- Risks and limitations section

Checklist:
- Are residual risks transparent?
- Are limitations described objectively?
- Can stakeholders understand what has not been verified?

---

### Step 6: Form conclusion and recommendation
Actions:
- Decide overall result (PASS / CONDITIONAL PASS / FAIL)
- Assess readiness for release, UAT, handoff, or next phase
- Define release conditions or follow-up actions if needed
- Keep the conclusion aligned with evidence and risks

Outputs:
- Final conclusion
- Recommendation
- Follow-up actions

Checklist:
- Is the conclusion explicit?
- Is the recommendation actionable?
- Is the conclusion supported by data and risks?

---

### Step 7: Review and publish report
Actions:
- Review the report for accuracy and completeness
- Validate summary numbers and defect references
- Share with stakeholders
- Archive the report and related evidence

Outputs:
- Final published test report
- Archived records for traceability

Checklist:
- Has the report been reviewed?
- Are data and references traceable?
- Is the final version shared with the right audience?

---

## 4. Outputs
The workflow should produce:
- Test report
- Defect summary
- Coverage summary
- Release/next-step recommendation
- Archived execution evidence

---

## 5. Roles Involved
Typical roles may include:
- QA / Tester
- QA lead
- Developer / Tech lead
- Product manager / Business owner
- Project manager / Release manager
- DevOps / Operations
- UAT representative

---

## 6. Review Points
Recommended review points:
- Execution data review
- Coverage review
- Defect/risk review
- Final conclusion review
- Stakeholder sign-off or acknowledgement

---

## 7. Exit Condition
The workflow is considered complete when:
- Execution data is summarized
- Coverage and defect status are documented
- Risks and limitations are transparent
- A conclusion and recommendation are given
- Stakeholders have received the final report
- Records are archived for future reference
