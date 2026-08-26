# Route / Recommend Regression Checklist

## Release Baseline

- [x] Forge release: `v1.2.1`
- [x] Corpus contract: v2.1.0 with explicit matched/skill/pack/confidence expectations
- [x] Vue migration cases assert selected variants and source/target-only domains
- [x] Every case asserts a pack ID or `null`
- [x] The black-box runner is authoritative: `python scripts/check-route-regression.py`

## Core Routing Boundaries

- [x] Test design selects `pack.general_test_plan`
- [x] Test implementation defeats test design for `帮我补一组单元测试`
- [x] Spring upgrade migration does not attach `pack.spring_review`
- [x] Production incident selects incident, not generic debug/error analysis
- [x] Spring review selects `pack.spring_review`
- [x] Playwright instability remains outside test-design ownership
- [x] Test reports select report plus `pack.general_test_report`
- [x] Release go/no-go selects release readiness plus `pack.release_readiness`
- [x] API/event producer-consumer compatibility selects contract compatibility
- [x] API topology/versioning design remains architecture-owned

## Confidence Calibration

- [x] Unmatched input produces `unmatched` diagnostics and exact low confidence
- [x] `--prefer` fallback uses configured low confidence with `prefer_fallback` diagnostics
- [x] Route and recommend fallback payloads expose matching diagnostic semantics
- [x] Single-candidate routes are policy capped
- [x] Keyword-only routes are policy capped
- [x] Tie-break margin is the original candidate gap and remains non-negative
- [x] Pack selection reports policy-disabled confidence promotion

## Configuration Safety

- [x] Semantic validation covers tie-break and every bias-rule keyword-set reference form
- [x] Semantic validation rejects unknown routing skill references
- [x] Semantic validation rejects inverted confidence-gap policy thresholds
- [x] Corpus evaluator validates bounded confidence and declared diagnostic fields

## Final Gate

- [x] Run `python -m forge_cli --root . validate --check semantics`
- [x] Run `python scripts/check-route-regression.py`
- [x] Run `python scripts/run-local-checks.py`
- [x] Record the final command outputs in the release delivery

The checklist is a release aid. The executable corpus and local quality gate remain the source of truth.
