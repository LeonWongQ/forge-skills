# Evidence-Driven Test Strategy Method

## Strategy Formulation

Digest the source into a compact evidence table. Segment by component, test layer, environment, failure type, and business risk. Look for concentration, recurrence, untested change surfaces, weak assertions, and slow or flaky feedback loops.

Map each risk to the cheapest layer that can prove it. Reserve E2E for critical cross-boundary journeys. Design representative success, boundary, invalid input, dependency failure, timeout, and regression cases according to risk.

## Gap Analysis

Assess behavior, branch/error, integration, data, environment, non-functional, and regression dimensions. A gap is actionable only when it names the missing behavior, likely impact, suitable layer, and evidence needed to close it.

## Assertion Calibration

Prefer semantic outcome assertions over existence or status-only checks. Add contract shape, state transition, persistence, side-effect, and negative assertions when those behaviors matter. Avoid snapshots for volatile data and assertions against implementation details.

## Test Health Diagnosis

Treat flaky rate, duration, defect escape, failure diagnosability, and maintenance cost as separate signals. Fixed waits, shared state, external dependencies, broad mocks, brittle selectors, and assertion-light tests require different remediations. Do not infer a root cause from one aggregate metric.
