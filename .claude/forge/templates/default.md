# Template: Default

## Purpose

This is the fallback template for tasks that do not require a specialized report structure.

Use this template when:
- the task is small or medium in scope
- the user wants a direct answer
- the task does not naturally fit review/debug/refactor/explanation formal structure
- a compact but still disciplined response is preferred

This template is intentionally lightweight, but it is not structure-free.

It should still preserve:
- a clear result
- a small amount of supporting reasoning
- visible uncertainty when relevant
- a practical next step when useful

---

## When to Use

Use the default template for tasks such as:

- short code review comments
- compact diagnosis summaries
- direct implementation suggestions
- brief tradeoff recommendations
- small explanation answers
- quick quality or risk checks
- lightweight follow-up answers in an ongoing conversation

If the task becomes substantial, prefer a specialized template.

---

## When Not to Use

Do not use this template when the task clearly needs:

- multiple ranked findings
- structured root-cause analysis
- phased refactor sequencing
- implementation rollout planning
- formal explanation sections
- persistent report artifact shape

In those cases, use a more specific template instead.

---

## Output Structure

The default structure is:

1. **Result**
2. **Key reasoning or findings**
3. **Risks or unknowns**
4. **Recommended next step**

These may be rendered as explicit sections or as a compact ordered answer depending on task size.

---

## Section Guidance

### 1. Result
Start with the direct answer, conclusion, or recommendation.

Examples:
- "The most likely issue is..."
- "I see one high-risk bug and one medium maintainability concern."
- "The safer approach is to..."
- "This looks correct under the shown assumptions, but..."

Do not bury the main result.

### 2. Key reasoning or findings
Include only the most important support.

Possible contents:
- strongest evidence
- core interpretation
- top one to three findings
- key tradeoff
- one important caveat

This section should be concise and decision-useful.

### 3. Risks or unknowns
Include this section when uncertainty affects the confidence or recommendation.

Examples:
- missing transaction call path
- no runtime validation
- partial code context only
- environment-dependent behavior not shown

If uncertainty is irrelevant, keep this very short or omit it.

### 4. Recommended next step
End with a useful next move if action is needed.

Examples:
- check whether the call crosses a Spring proxy
- replace the fixed wait with a condition-based assertion
- validate the query with `EXPLAIN`
- split the change into a fix first and refactor later

If no action is needed, a short closure is enough.

---

## Style Guidance

- keep it concise
- lead with value
- preserve evidence-awareness
- avoid padded ceremony
- use explicit uncertainty when it matters
- do not imitate a formal report if a short answer is better

This template should feel disciplined, not bureaucratic.

---

## Good Fit Examples

### Example 1: compact code judgment
"This can return stale data because the cache invalidation happens before the transaction commits."

### Example 2: small diagnosis answer
"The timeout is most likely caused by a fixed wait combined with slower CI rendering."

### Example 3: lightweight implementation suggestion
"A safer first step is to isolate validation logic before changing transaction boundaries."

These are all cases where a specialized report would be heavier than necessary.

---

## Relationship to Other Templates

The default template is the lowest-friction output contract.

Use it when:
- specialized structure would add overhead without adding value

Do not confuse it with:
- unstructured freeform output
- no-template mode
- shortcut mode that skips reasoning discipline

The default template still expects:
- a result
- support
- visible uncertainty when relevant
- actionable closure

---

## Short Reminder

Default means:
- answer first
- justify briefly
- note uncertainty if it matters
- leave the user with a useful next step
