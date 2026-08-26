# Route / Recommend Regression Record

<!-- forge-facts: route-regression-count=81 -->

## Metadata

- Release: `v1.2.1`
- Corpus: `registry/route-regression.json` v2.1.0
- Router policy: `registry/skill-routing.json` confidence policy v1
- Authoritative command: `python scripts/check-route-regression.py`

The executable corpus is authoritative. This document describes its contract and the expected runner summary; it is not a hand-maintained list of historical route outputs.

---

## Corpus Contract

Each case declares:

- `category`: intent, collision, pack, no-match, calibration, paraphrase, or historical coverage
- `mode`: `route`, `recommend`, or `ask`
- Ask cases additionally assert ownership decisions (`decision`, `host_action`, `reason_code`, and `native_id` when relevant).
- `input`, plus an optional `preferred_skill` for explicit fallback coverage
- exact `matched`, `skill`, and `pack` expectation; `pack: null` asserts pack abstention
- optional selected `variant`, exact domains, or forbidden domains for composition-sensitive cases
- bounded confidence (`min` / `max`)
- optional forbidden skills/packs
- optional diagnostics keys for evidence-sensitive calibration cases

The v1.2.1 corpus has 78 cases. Its runner reports mode/category totals and observed confidence distribution in addition to pass/fail status.

---

## Confidence Diagnostics

JSON route and recommend payloads include `confidence_diagnostics`:

| Field | Meaning |
|---|---|
| `base_confidence` | Confidence derived from the natural candidate situation before caps. |
| `final_confidence` | Post-cap confidence; equal to the existing top-level `confidence`. |
| `selection_mode` | `ordinary`, `tie_break`, `prefer_fallback`, or `unmatched`. |
| `candidate_count` | Number of scored skill candidates before selection. |
| `runner_up_score` / `margin` | Competitive evidence. Tie-break margin is the original top-two gap, never a negative post-selection artifact. |
| `matched_trigger_count` / `keyword_evidence_count` | Direct trigger and keyword-bias evidence counts. |
| `caps` | Applied confidence caps, including keyword-only, single-candidate, tie-break, fallback, or unmatched. |
| `pack_promotion` | `disabled_by_policy` when a pack is selected; packs do not promote skill confidence in policy v1. |

Policy consequences protected by the corpus:

- unmatched inputs are low confidence;
- `--prefer` fallback uses configured low confidence rather than pretending natural evidence exists;
- single-candidate and keyword-only selection are capped;
- tie-break diagnostics retain a meaningful original race margin;
- route and recommend project the same diagnostics;
- pack selection contributes composition but not confidence promotion.

---

## Historical Boundaries Retained

The corpus preserves the prior high-value fixes while using current, executable expectations:

- test reports are owned by `skill.report`, not test design;
- Playwright/E2E instability is not captured by test design;
- migration requests do not receive the Spring review pack;
- direct test-implementation wording wins its test-design collision with medium, tie-break-capped confidence;
- explicit go/no-go readiness owns release decisions, while upgrade/cutover/rollback planning remains migration-owned;
- explicit producer/consumer contract compatibility wins close migration collisions, while future API topology remains architecture-owned.

---

## Release Verification

Run:

```bash
python scripts/check-route-regression.py
python -m forge_cli --root . validate --check semantics
python scripts/run-local-checks.py
```

A passing release requires all corpus cases to pass. The corpus covers route/recommend selection and `ask` ownership decisions. The corpus output—not stale prose tables—defines the current compatibility contract.
