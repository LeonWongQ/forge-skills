# Vue Version Routing Contract

Read this reference only when the target artifact is Vue-related.

Identify the target package and verify its resolved `vue` version from a lockfile or installed dependency metadata before loading framework guidance. `package.json` is provisional when no resolved version exists. `.vue` files, Vite, Composition API, `<script setup>`, Router, and `import.meta.env` are not version proof.

- Vue 2.0 through 2.6: load `domain.vue2`; verify compiler parity and, for vmd-ui, its resolved version, imports, registration, and CSS/theme use.
- Vue 2.7: load `domain.vue2_7`; verify the runtime, compiler, and Vite-compatible plugin/toolchain.
- Vue 3: load `domain.vue3_vite`.
- Missing or conflicting evidence: keep the current intent workflow, request or discover the target package/version, and do not mix lifecycle, reactivity, compiler, or build guidance across versions.

Intent ownership remains with the active specialized Skill. `page-test` owns browser E2E work, `test-implementation` owns component/unit tests, and review/debug/refactor/optimize requests retain their respective Skills even when a Vue version is known.
