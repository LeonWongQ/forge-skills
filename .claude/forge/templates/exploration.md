# Template: Exploration

## Purpose

This template shapes the output of pre-orientation exploration tasks — scope discovery, option enumeration, situation assessment, and problem-space mapping.

Use this template when:
- the user asks to explore or understand a codebase area before acting
- the problem space is ambiguous and needs scoping
- the user wants options enumerated without premature narrowing
- the task is "先看看 / 摸清现状 / 梳理一下 / 先调研"

This template keeps output lightweight and scannable. It should not feel like a formal report — it's a structured map that helps the user decide what to do next.

---

## When to Use

Use the exploration template for tasks such as:

- codebase area discovery before committing to plan/debug/refactor
- module or service landscape mapping
- option enumeration for multi-path decisions
- pre-orientation assessment: "what's here and what matters"
- scope discovery before test planning or migration planning
- any "先看看" / "先摸清楚" request

---

## When Not to Use

Do not use this template when:

- the task has a clear single mode (review, debug, plan, refactor, explain, document)
- the user wants a definitive root cause (use `template.debug_report`)
- the user wants an implementation plan (use `template.implementation_plan`)
- the user wants a formal report (use `template.review_report` or `template.test_report`)
- the answer is a simple fact or concept explanation (use `template.explanation` or `template.default`)

---

## Output Structure

The exploration output has five sections, each serving a distinct purpose:

1. **Current Understanding** — clarify what the user is asking
2. **Landscape** — map the relevant territory
3. **Observations** — note what stands out
4. **Possible Directions** — enumerate viable paths
5. **Recommended Next Step** — concrete action

For small explorations, sections may be compact (one paragraph each).
For substantial explorations, each section should have enough substance to be decision-useful.

---

## Section Guidance

### 1. Current Understanding

Restate the user's question in your own words to confirm alignment.

Include:
- what the user is asking (clarified, not assumed)
- what is already known
- what is still unknown or needs investigation

Start with: "You're asking to..."

Keep this tight — one to three sentences.

### 2. Landscape

Map the relevant territory at appropriate depth.

Include:
- relevant modules / services / components — names and roles
- key relationships and dependencies
- scope boundaries — what's in scope, what's adjacent

Use structure when the landscape is large:
- bullet lists for components
- brief role annotations for each

Do not dump file listings. Describe the shape and relationships.

### 3. Observations

Note what stands out — patterns, surprises, gaps, risk areas.

This is not a judgment section ("this is bad"). It's a signal section ("this is notable").

Each observation should be:
- specific and grounded in what you found
- connected to a potential implication
- brief enough to scan

Examples:
- "The service layer has no interface abstraction — any refactor would need to work around concrete class coupling."
- "Three modules share a similar pattern but with divergent error handling — worth standardizing."
- "Test coverage is concentrated in the service layer; controller and repository layers are thin."

### 4. Possible Directions

Enumerate viable paths without prematurely narrowing.

For each direction:
- a short label (Option A, Option B, ...)
- what it would look like
- when it fits best
- key tradeoff or risk

Keep options distinct. Avoid presenting the same option with different wording.

Two to four options is typical. One option means you haven't explored enough.
More than five means you should group or prioritize.

### 5. Recommended Next Step

End with one concrete, actionable next step.

Include:
- suggested task mode: review / debug / plan / refactor / ...
- what additional information would help (if any)
- one specific action the user can take or ask for

Examples:
- "Suggested mode: **plan** — now that the landscape is mapped, create an implementation plan for the API layer refactor."
- "Suggested mode: **debug** — the connection pool pattern needs investigation. Ask: '帮我排查这个连接池泄漏问题'."
- "Before committing to a direction, we need to clarify: [specific question for the user]."

---

## Style Guidance

- lead with clarity, not ceremony
- use structure to make scanning easy (headings, bullets, short paragraphs)
- keep observations evidence-grounded, not judgmental
- enumerate options with tradeoffs, not advocacy
- end with a concrete next step, not an open-ended "以上"
- match depth to task size — small exploration, compact output

---

## Relationship to Other Templates

| Template | Use when |
|----------|----------|
| `template.exploration` | Scoping and discovery before committing to a mode |
| `template.default` | Short answer, compact recommendation, general fallback |
| `template.debug_report` | Root cause analysis, failure diagnosis |
| `template.implementation_plan` | Feature plan, fix plan, rollout plan |
| `template.review_report` | Code review, change review, risk review |
| `template.explanation` | Mechanism explanation, concept teaching |

Exploration sits at the **front** of the decision pipeline — it maps the space before other templates take over.

---

## Short Reminder

Exploration means:
- clarify the question first
- map the landscape honestly
- note what stands out
- enumerate paths with tradeoffs
- recommend one concrete next step

Do not rush to conclusions. Do not over-formalize. Make the output scannable and decision-useful.
