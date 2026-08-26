---
name: bailian-workflow
description: Safely inspect, decrypt, extract, edit, validate, orchestrate, rebuild, and encrypt Alibaba Bailian workflow import artifacts. Use for Bailian/DashScope workflow configuration, encrypted .enc imports, SCRIPT or prompt assets, multi-workflow orchestration, import-key handling, and compatibility-preserving configuration changes.
---

# Bailian Workflow

Read [workflow-tools.md](references/workflow-tools.md) before operating on an artifact. Resolve the project-owned configuration tool from `BAILIAN_WORKFLOW_TOOLS_DIR`, then `.bailian/workflow-config-tools` under the current project, then the documented compatibility path. Confirm the selected local directory before running it.

## Safety Boundary

- Before any operation that reads or writes encrypted content, ask the user to confirm an import-key source: an environment-variable name, a protected local key-file path, or permission to use local masked input. Explicitly tell them not to paste the key into chat. Do not proceed when no source is confirmed.
- Ask for the source, not a key pasted into chat: prefer the name of a session environment variable; otherwise accept a protected key-file path or a local masked terminal prompt. Never print, embed, or commit import keys, API keys, decrypted JSON, extracted prompts, or encrypted artifacts.
- Use `--key-env` by default. Accept `--key-file` only for a protected local file; use `--key-stdin` only when automation explicitly requires it. Never put a key in a shell argument.
- Treat the Bailian AES-256-ECB plus PKCS#7 format as an import-compatibility constraint, not a general encryption recommendation. Do not replace it unless the target platform format changes.
- Inspect before extraction; write only to new workspace and output paths. Never overwrite the source `.enc`, an existing workspace, or an existing output artifact.
- Keep unknown nodes, edges, model/provider settings, tenant fields, and unmanaged asset fields unchanged. Do not infer mappings or business rules.

## Standard Flow

1. Identify the input artifact, the selected workflow version, the desired assets/nodes, the private output locations, and the manual import owner.
2. Ask the user for the import-key source. Confirm the environment-variable name, protected key-file path, or their approval to enter it through a local masked prompt before using any encryption-related command.
3. Run `inspect` and confirm the selected version before extracting anything.
4. Run `extract` into a new private workspace. Edit only files represented by `manifest.json` under `assets/`.
5. Run `validate`, then `plan`. Validation must include Bailian SCRIPT compatibility checks, not only CPython syntax. Resolve any source-versus-workspace conflict with the user; never force a conflict resolution.
6. For SCRIPT assets, run `script-test` only with a project-owned fixture and an explicit entrypoint. Treat it as behavior evidence, not import-compatibility evidence.
7. Run `build` to a new `.enc` output. It validates, encrypts, decrypts, and structurally compares the result.
8. Run a final read-only `inspect`. Platform import and release remain a user-controlled manual action.

## Orchestration Rules

- Model a multi-workflow process as explicit stage inputs and outputs. Validate each handoff's field names, required values, error branch, timeout, and idempotency behavior before changing the workflow.
- Preserve the existing order and contract of each workflow unless the user explicitly asks to alter it. Do not silently join outputs from multiple workflows.
- Prefer narrow changes to one manifest-owned asset or node at a time, then validate and rebuild. Treat version creation, credential rotation, and platform publishing as separately authorized operations.

## Bailian SCRIPT Compatibility

- Bailian imports a restricted Python subset. A script that parses and runs under CPython can still fail during platform compilation.
- Keep exactly one top-level entrypoint in each SCRIPT asset. Inline small parsing and transformation helpers instead of adding another `def` or `async def`; the platform may rewrite helper symbols with a leading `*` and reject them as invalid variable names.
- Reject `*args`, `**kwargs`, starred call/list/tuple/set unpacking, and dictionary `**` unpacking before `plan` or `build`.
- Do not use `getattr()` in SCRIPT assets; the sandbox does not provide it. Read declared start-node inputs directly (for example, `params.message`) or use explicit dictionary access when the value is a dictionary. Require the input contract to establish required attributes instead of emulating optional access through reflection.
- A successful `ast.parse`, `py_compile`, or local `script-test` is necessary but insufficient. Do not build or report import readiness unless the project workflow tool's platform-compatibility validator passes every SCRIPT asset.

## Completion Criteria

Report the selected version, intended node/asset changes, validation result, conflict result, output path, encrypt-then-decrypt verification result, and any manual import/rollback step. Do not report secrets or plaintext content.
