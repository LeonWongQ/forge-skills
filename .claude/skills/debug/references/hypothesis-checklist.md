# Debug Hypothesis Checklist (condensed from debug-checklist.md)

## Symptom Definition
- [ ] What: exact error or behavior stated
- [ ] Where: class, method, module boundary identified
- [ ] When: always / intermittent / first occurrence / after trigger
- [ ] Conditions: specific inputs, environment, timing, concurrency

## Evidence Quality
- [ ] Direct observations collected (not assumed)
- [ ] Stack traces are full, not truncated
- [ ] Logs include timestamps and surrounding context
- [ ] Configuration is runtime values, not assumed defaults
- [ ] Recent changes checked (git log)

## Hypothesis Quality
- [ ] Multiple hypotheses generated (minimum 2, prefer 3+)
- [ ] Each hypothesis has supporting evidence
- [ ] Each hypothesis has contradicting evidence (if any)
- [ ] Each hypothesis has a test to confirm or eliminate
- [ ] Hypotheses ranked by evidential likelihood; operational impact reported separately
- [ ] First plausible explanation is NOT assumed to be the root cause

## Root Cause Quality
- [ ] Established root cause includes trigger, mechanism, and enabling condition
- [ ] Unestablished root cause is labeled with confidence, missing evidence, and a falsifier
- [ ] Root cause is NOT just "the error on line X"

## Fix Quality (only when remediation was requested)
- [ ] Fix addresses the diagnosed mechanism (not just symptom suppression)
- [ ] Verification plan included
- [ ] Regression risk assessed
