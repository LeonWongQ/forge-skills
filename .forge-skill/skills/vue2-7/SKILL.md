---
name: vue2-7
description: >-
  Implement or evolve confirmed Vue 2.7 applications, including verified
  Vue 2.7 + Vite-compatible projects. Requires explicit Vue 2.7 version
  evidence and validates the target project's runtime, compiler, and build
  plugin before applying framework guidance. Specialized review, debug,
  refactor, test, and E2E skills retain ownership of their explicit intents.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
---

# Vue 2.7

## Activation Sequence

1. Load the Forge kernel and AUTOLOAD policy.
2. Confirm explicit Vue 2.7 intent. Vite, Composition API, `<script setup>`, and `.vue` are not enough to select this skill.
3. Identify the target package and confirm a resolved `vue` version of `2.7.x` from its lockfile or installed dependency metadata.
4. Inspect the actual compiler/SFC setup and, where Vite is present, the configured Vue 2-compatible plugin, aliases, dependency prebundling, assets, and build-path conventions.
5. Load `domain.vue2_7`; load testing or Playwright domains only when evidence requires them.
6. Preserve Vue 2 bootstrap, lifecycle, global API, and reactivity semantics unless a migration is explicitly scoped.
7. Run relevant existing tests/build commands and distinguish executed checks from unverified compatibility.

## Composition

- Domain: `domain.vue2_7`
- Template: `template.implementation_plan`
- Checklists: general-quality, verification, delivery
- Workflow: `workflow.full_default`

## Boundaries

- Vue 2.0–2.6 → `vue2`
- Vue 3 → `vite-vue3`
- Generic Vite/Vue without a confirmed version → request project evidence or use the original intent skill
- Review/debug/refactor/optimize/test/E2E intent → existing specialized skill with the version-matching domain

## Delivery Guard

- [ ] Target package has a resolved Vue `2.7.x` version.
- [ ] Vite/plugin/compiler assumptions were verified from the project rather than inferred.
- [ ] Vue 3 `createApp` and app-instance APIs were not introduced by accident.
- [ ] Relevant existing verification scripts were run when available.
- [ ] Version conflicts or remaining uncertainty are explicit.
