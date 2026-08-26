# Domain: Vue 2.7

## 1. Activation and Version Evidence

Load this domain only when the target package resolves `vue` to exactly `2.7.x`. Prefer the lockfile or installed dependency metadata for the target package over a broad manifest range.

Vue 2.7 is a compatibility release, not proof of Vue 3. Vite, Composition API, `<script setup>`, `.vue`, Vue Router, and `import.meta.env` may occur in a Vue 2.7 project and must not select Vue 3 guidance. Confirm the runtime version before selecting APIs, compilers, test tools, or build plugins.

---

## 2. Runtime and Application Heuristics

- Preserve the target project's Vue 2 bootstrap, Options API, lifecycle, global API, router, store, and reactive-state conventions unless a migration is explicitly requested.
- Do not assume Vue 3 `createApp` or app-instance behavior from Composition API or Vite evidence.
- Keep Vue 2 reactivity limitations in view: use the existing `$set`/`Vue.set`, `$delete`/`Vue.delete`, `splice`, or replacement patterns where required.
- Use `mounted`, `beforeDestroy`, `destroyed`, and `$nextTick()` according to the existing runtime, not Vue 3 lifecycle names.

## 3. Vue 2.7 + Vite Compatibility Checks

Before modifying a Vite-based Vue 2.7 project, inspect the actual plugin, SFC/compiler arrangement, dependency prebundling behavior, aliases, CSS/assets, and build path settings.

- A Vite config is not enough to infer Vue 3; confirm the installed Vue major/minor and the plugin configured for it.
- Do not independently upgrade Vue, compiler packages, Vite plugins, `vue-loader`, or UI libraries as part of a feature change.
- Validate dev-server versus production-build behavior after changing base paths, assets, dynamic imports, aliases, or environment handling.

## 4. Testing and Verification

- Select the test utility/compiler transform from actual project dependencies and configuration; do not apply Vue 3 mounting assumptions to Vue 2.7.
- Keep component/unit testing separate from Playwright E2E. Load `domain.testing` or `domain.playwright` only when their scope is present.
- For mixed Vue 2.7/Vue 3 monorepos, scope all conclusions to the target package and report cross-package version conflicts explicitly.
