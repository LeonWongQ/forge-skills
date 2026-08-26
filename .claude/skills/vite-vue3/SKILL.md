---
name: vite-vue3
description: >-
  Implement or evolve Vue 3 and Vite components, pages, composables, routes,
  stores, configuration, and component-level behavior using evidence from the
  target project. Use only when the request explicitly concerns Vue 3 or the
  target package is confirmed to resolve Vue 3.x. Vite, `.vue`, Composition API,
  and script setup alone do not prove Vue 3; Vue 2, Vue 2.7, Vue CLI/Webpack,
  and vmd-ui requests use their version-matching path. Review, debugging,
  refactoring, optimization, test implementation, and Playwright E2E requests
  retain their specialized skills.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
---

# Vite + Vue 3

## 1. Activation Sequence

1. Load `.claude/forge/CLAUDE.md` and `.claude/forge/AUTOLOAD.md`.
2. Confirm explicit Vue 3 intent or inspect the target package's lockfile/resolved dependency metadata for Vue `3.x`. Vite, `.vue`, Composition API, and `<script setup>` are not enough; route confirmed Vue 2/2.7 work to its version-matching skill and ask for evidence when version is uncertain.
3. Inspect project evidence before selecting implementation details:
   - `package.json`, lockfiles, package-manager scripts
   - `vite.config.*`, `vitest.config.*`, TypeScript configuration
   - `.vue` components, composables, routes, stores, and existing tests
   - installed Vue Router, Pinia, component-library, Vitest, Vue Test Utils, and Playwright dependencies
4. Load `.claude/forge/domains/vue3-vite.md`.
   - Add `domains/testing.md` only when tests are in scope.
   - Add `domains/playwright.md` only when browser/E2E evidence is in scope.
5. Define the requested behavior, existing public contracts, and acceptance criteria before editing.
6. Implement narrowly, matching the project's component, styling, state, routing, and test conventions.
7. Run only relevant existing project scripts; report what ran and what remains unverified.

## 2. Forge Module Composition

| Module | Selection | Role |
|--------|-----------|------|
| Domain | `domain.vue3_vite` | Confirmed Vue 3, Vite, router, store, build, and component heuristics |
| Domain | `domain.testing` when tests change | Test quality, isolation, and coverage discipline |
| Domain | `domain.playwright` for E2E evidence | Browser automation, locator, wait, and CI rules |
| Template | `template.implementation_plan` | Scope, approach, implementation, and verification output |
| Checklists | general-quality, verification, delivery | Baseline quality and bounded claims |
| Workflow | `workflow.full_default` | Discover → evidence → context → reasoning → planning → execution → verification → delivery |

## 3. Implementation Discipline

- Do not assume TypeScript, Pinia, Vue Router, SSR, a component library, Vitest, or a package manager without repository evidence.
- Preserve component props/emits, route, store, and environment contracts unless the request explicitly changes them.
- Keep reactive state ownership clear; model loading, empty, error, and stale-async states where applicable.
- Follow existing Vite aliases, environment exposure, asset, and deployment-path conventions.
- Prefer component/unit tests for component behavior; use Playwright only for browser user journeys.
- Do not treat `VITE_` environment values as secret because they are exposed to browser code.

## 4. Boundary with Other Skills

| Request | Use instead |
|---------|-------------|
| Review confirmed Vue 3/Vite code | `code-review` with `domain.vue3_vite` |
| Diagnose a confirmed Vue 3/Vite failure | `debug` with `domain.vue3_vite` |
| Refactor confirmed Vue 3 components/composables | `refactor` with `domain.vue3_vite` |
| Optimize confirmed Vue 3 rendering or bundle behavior | `optimize` with `domain.vue3_vite` |
| Write confirmed Vue 3 component tests | `test-implementation` with `domain.vue3_vite` |
| Write confirmed Vue 3 page/browser E2E tests | `page-test` with `domain.playwright` and `domain.vue3_vite` |

## 5. Delivery Guard

Before delivering:

- [ ] Vue/Vite project evidence was inspected before selecting tools or patterns.
- [ ] Props/emits, reactivity, router/store, and Vite configuration contracts are preserved or intentionally changed.
- [ ] Relevant loading/error/async behavior is handled.
- [ ] Existing project scripts were used when available and relevant.
- [ ] Testing and E2E scope are delegated to the appropriate existing skill.
- [ ] Verification results and remaining uncertainty are explicit.
