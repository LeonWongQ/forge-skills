# Domain: Vue 2

## 1. Activation and Version Evidence

Load this domain only when the target package resolves `vue` to `2.0.x` through `2.6.x`. Prefer the target package lockfile or installed dependency metadata; treat `package.json` as provisional only when resolved evidence is unavailable.

Supporting evidence includes `new Vue(...)`, `Vue.use(...)`, `Vue.extend`, Options API components, `vue-template-compiler`, Vue CLI/Webpack configuration, and Vue Test Utils v1. Check that the project's compiler/SFC setup is compatible with the resolved Vue version; a mismatch is a compatibility risk, not evidence for Vue 3.

Do not introduce `createApp`, Vue 3 global APIs, Pinia, or Vite-specific assumptions solely because related files exist elsewhere in a workspace.

---

## 2. Vue 2 Implementation and Review Heuristics

- Follow the existing Options API, plugin registration, router, Vuex/store, and component-registration conventions.
- Component `data` must return a fresh object; preserve `this` binding and public props/events/slots contracts.
- Vue 2 cannot observe direct addition/deletion of reactive object properties, direct array index assignment, or array-length mutation. Use the established `$set`/`Vue.set`, `$delete`/`Vue.delete`, `splice`, or whole-object replacement pattern as appropriate.
- Put DOM-dependent work in `mounted`; after reactive changes, wait for `$nextTick()` before measuring or calling DOM-dependent integrations. Clean up timers, listeners, and subscriptions in `beforeDestroy`/`destroyed`.
- Preserve Vue CLI/Webpack, alias, asset, `process.env`, and `NODE_ENV` conventions unless a build migration is explicitly scoped.

## 3. vmd-ui Compatibility Gate

Apply vmd-ui guidance only after inspecting the target package's manifest, lockfile, resolved package metadata, and existing application imports.

- Confirm the exact dependency name/version, peer dependency requirements, module format, CSS/theme/asset entry points, and current `Vue.use(...)` or component registration pattern.
- Preserve documented component props, emitted events, slots, validation, and theme contracts from the installed version; do not invent or rely on private APIs or undocumented `$refs` behavior.
- Import the documented style/theme entry exactly once and verify production build asset handling.
- Prefer local adapters for application-specific defaults or event normalization, reducing future UI-library migration impact.

## 4. Testing and Verification

- Use the project's Vue 2-compatible test tooling, commonly Vue Test Utils v1, only when present.
- Keep global plugin installation test-local where the project pattern supports it; await `$nextTick()` and pending promises before DOM assertions.
- Run relevant existing tests and a production build before changing compiler, VMD UI, CSS/theme, or Webpack configuration.
- Vue 2 is legacy software; surface maintenance and compatibility exposure rather than silently upgrading runtime, compiler, or UI libraries.
