---
name: vue2
description: >-
  Implement or evolve confirmed Vue 2.0–2.6 applications, Vue CLI/Webpack
  configuration, and verified vmd-ui integrations using target-project evidence.
  Requires an explicit Vue 2 version signal and verifies the resolved runtime
  before implementation. Review, debugging, refactoring, testing, and E2E
  requests retain their specialized skills.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
context: fork
---

# Vue 2

## Activation Sequence

1. Load the Forge kernel and AUTOLOAD policy.
2. Confirm explicit Vue 2.0–2.6 intent; never select this skill from a generic `.vue`, Vue, Vite, or Composition API reference.
3. Locate the target package. Inspect its lockfile or installed metadata for the resolved `vue` version; use `package.json` only as provisional evidence when needed.
4. Confirm compiler/toolchain consistency, including `vue-template-compiler` or the project's actual SFC setup. Report mismatch or ambiguity instead of guessing a Vue version.
5. Load `domain.vue2`. Load testing or Playwright domains only when their scope is present.
6. For vmd-ui, inspect the resolved package version, peer dependencies, existing imports/registration, and CSS/theme entry before changing any library integration.
7. Follow existing Options API, router/store, component, and build conventions; run relevant existing scripts and report verification boundaries.

## Composition

- Domain: `domain.vue2`
- Template: `template.implementation_plan`
- Checklists: general-quality, verification, delivery
- Workflow: `workflow.full_default`

## Boundaries

- Vue 2.7 → `vue2-7`
- Vue 3 → `vite-vue3`
- Review/debug/refactor/optimize/test/E2E intent → existing specialized skill with the version-matching domain

## Delivery Guard

- [ ] Target package and resolved Vue 2.0–2.6 version were identified.
- [ ] Compiler/toolchain compatibility was checked.
- [ ] vmd-ui APIs were used only after inspecting the installed package and current local usage.
- [ ] Vue 3 APIs and Vite assumptions were not introduced without explicit migration evidence.
- [ ] Executed verification and remaining uncertainty are stated.
