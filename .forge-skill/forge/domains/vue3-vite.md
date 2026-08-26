# Domain: Vue 3 + Vite

## 1. Activation and Version Evidence

Load this domain only after confirming that the **target package** resolves `vue` to `3.x`. Use the target package's lockfile or installed dependency metadata first; use `package.json` only as provisional evidence when no resolved version is available.

Supporting signals such as `createApp`, `@vitejs/plugin-vue`, and Vue 3 compiler/runtime configuration can corroborate the result. Do **not** treat `.vue`, Vite, Vue Router, Composition API, `<script setup>`, or `import.meta.env` as sufficient Vue 3 evidence: Vue 2.7 projects can overlap.

If evidence is absent or conflicts, request the target package/version. Do not load this domain for Vue 2, Vue 2.7, Vue CLI/Webpack legacy applications, or vmd-ui projects unless the target package itself is confirmed Vue 3.

---

## 2. Vue 3 and Vite Heuristics

- Preserve props/emits, router, store, and environment contracts unless a change is requested.
- Follow the project convention for Composition API and `<script setup>`; keep ownership of refs, computed values, watchers, async state, and cleanup explicit.
- Use `createApp`, Pinia, and Vue 3 lifecycle/global APIs only after the version gate passes and only when those dependencies are actually present.
- Match the existing Vite plugin, aliases, `base`, asset URL, dynamic import, and `import.meta.env` conventions. `VITE_` values are browser-exposed and are not secrets.
- Treat dev-server proxy behavior as development tooling unless deployment evidence says otherwise.

## 3. Testing and Browser Boundaries

- Use the project’s actual Vue 3-compatible test stack; assert rendered behavior and emitted contracts.
- Load `domain.testing` for test quality and `domain.playwright` only for browser/E2E work.
- Vite, a `.vue` file, or a component library alone does not justify Vue 3 test-tooling assumptions.

## 4. Verification

- Verify the resolved Vue 3 version before selecting runtime APIs.
- Run existing type-check, test, lint, build, and E2E scripts only when present and relevant.
- Verify production-path assumptions after changing Vite base paths, assets, environment variables, or dynamic imports.
- State executed and unexecuted checks explicitly.
