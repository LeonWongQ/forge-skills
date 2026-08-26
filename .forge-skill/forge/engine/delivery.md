# Engine: Delivery

## Purpose

Delivery converts the work into a final response the user can actually use.

This stage is not a cosmetic afterthought.
It determines whether the value created by the earlier stages becomes:
- understandable
- actionable
- appropriately scoped
- easy to trust
- easy to apply

Delivery exists to prevent:
- technically correct but unusable responses
- buried conclusions
- missing next steps
- loss of uncertainty signals
- mismatch between task and output shape

Delivery is where engineering work becomes user-facing value.

---

## Core Objective

Present the outcome in a form that is clear, accurate, useful, and aligned with the selected template.

A strong Delivery stage should answer:

- What is the result?
- What matters most?
- What evidence or reasoning supports it?
- What should the user do next?
- What remains uncertain?
- How should the user interpret confidence and risk?

---

## Inputs

Delivery uses:

- outputs from previous engine stages
- selected template
- active behavior emphasis
- user communication style and goal
- checklist results
- confidence and risk information

Delivery may involve:
- concise answer
- structured report
- review summary
- debug diagnosis
- refactor plan
- implementation guidance
- explanation document

---

## Outputs

Delivery should produce a final response that contains some combination of:

- direct result or conclusion
- prioritized findings
- supporting evidence or rationale
- recommended next steps
- risks
- open questions
- confidence statement
- structured formatting aligned with template

---

## Delivery Responsibilities

### 1. Lead with value
Start with the answer, conclusion, or current best result.

Do not force the user to read the whole response to discover the outcome.

### 2. Match the task shape
A review should read like a review.
A debug diagnosis should read like a diagnosis.
An explanation should read like an explanation.

### 3. Preserve important distinctions
Keep separate:
- fact vs assumption
- finding vs suggestion
- verified vs unverified
- in-scope vs adjacent concern

### 4. Make next steps usable
Recommendations should be concrete enough to act on.

### 5. Keep detail proportional
Provide enough structure and depth to be useful without turning every response into ceremony.

---

## Delivery Process

### Step 1: Determine the delivery mode
Choose whether the final output should be:
- concise
- structured
- report-like
- action-plan oriented
- explanation-oriented

This should usually follow the selected template.

### Step 2: Lead with the result
Examples:
- "The most likely root cause is..."
- "I found three meaningful issues..."
- "The refactor should be split into two safe steps..."
- "This query is likely slow because..."

### Step 3: Present supporting content in priority order
Usually:
1. most important conclusion
2. evidence or reasoning
3. risks / uncertainty
4. next steps

### Step 4: Preserve verification honesty
State what is confirmed and what is not.

### Step 5: End with useful action
Conclude with:
- a recommendation
- a next diagnostic request
- a safe implementation sequence
- a validation instruction
- a summary of decisions

---

## Delivery by Task Type

### Review delivery
Should emphasize:
- findings
- severity or priority
- why each issue matters
- suggested fixes
- overall risk posture

### Debug delivery
Should emphasize:
- symptom
- ranked hypotheses or root cause
- supporting evidence
- confidence
- fix and validation path

### Refactor delivery
Should emphasize:
- structural problem
- proposed transformation
- safety controls
- staged plan
- verification

### Optimize delivery
Should emphasize:
- bottleneck
- evidence basis
- recommended optimization
- expected impact
- tradeoffs
- measurement plan

### Document delivery
Should emphasize:
- clarity
- accuracy
- audience utility
- navigable structure

### Explain delivery
Should emphasize:
- concept definition
- why it matters
- mechanism
- example
- pitfalls

---

## Output Ordering Guidance

A generally effective ordering pattern is:

1. direct answer / summary
2. key findings or diagnosis
3. supporting evidence / reasoning
4. risks / unknowns
5. recommended next steps

For short responses, these can be compressed.
For structured reports, they should appear as explicit sections.

---

## Delivery Tone and Style

### Direct
Avoid hiding conclusions behind excessive setup.

### Grounded
Do not sound more certain than the work justifies.

### Useful
Prioritize the user's next action.

### Structured
Use sections, bullets, or ordering when they improve scanability.

### Proportionate
Avoid over-formatting trivial tasks and under-formatting complex ones.

---

## Handling Blocked Delivery

Sometimes the task cannot be completed fully.

In that case, delivery should still provide:

- what is known
- what is unknown
- why the unknown matters
- what specific data is needed next
- what partial recommendation is still safe

### Example
"I can review the method-level logic, but I cannot confirm transaction behavior without seeing how this service is invoked and whether the call crosses a Spring proxy boundary."

This is better than either:
- pretending certainty
- refusing to help entirely

---

## Delivery of Uncertainty

Uncertainty should be visible but not paralyzing.

Good uncertainty delivery:
- "Most likely..."
- "High confidence in the null-handling issue; medium confidence in the transaction concern because invocation context is missing."
- "The fix appears correct by static review, but concurrency behavior remains unverified."

Bad uncertainty delivery:
- vague hedging everywhere
- mixing confidence levels without explanation
- hiding uncertainty until the end

---

## Template Adherence

Delivery should respect the selected template without becoming mechanically rigid.

### Template should shape:
- section ordering
- field expectations
- degree of structure

### Template should not force:
- repetitive filler
- irrelevant sections
- unnatural phrasing

If the template and the user's explicit need conflict, prefer user usefulness while preserving core structure where possible.

---

## Delivery Anti-Patterns

### Anti-pattern 1: buried conclusion
Making the main answer hard to find.

### Anti-pattern 2: evidence dump without synthesis
Listing observations without telling the user what they mean.

### Anti-pattern 3: recommendation without rationale
Telling the user what to do without explaining why.

### Anti-pattern 4: unscoped confidence
Speaking with certainty while omitting what was not checked.

### Anti-pattern 5: mismatched format
Giving a debug report when the user needed a quick explanation, or vice versa.

### Anti-pattern 6: no next step
Ending the response without helping the user act.

---

## Delivery Completion Criteria

Delivery is sufficient when the final response clearly communicates:

1. the result or current best conclusion
2. the most important supporting findings
3. what is verified vs uncertain
4. the practical next step
5. the risk or confidence posture
6. the content in a form appropriate to the task

If these are unclear, delivery is incomplete.

---

## Short Reminder

Before finalizing, ensure:
- the answer leads with value
- important findings are prioritized
- uncertainty is visible
- next steps are actionable
- the structure matches the task
