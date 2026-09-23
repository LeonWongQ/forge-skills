---
name: codex-hook-doctor
description: >-
  Codex-specific extension for the main hook-doctor Skill. Use for Codex
  Desktop or CLI app-server discovery, enabled and trust status, Trust UI,
  trust-hash behavior, and Codex-native Stop evidence. Use hook-doctor as the
  primary workflow for shared configuration and capture diagnosis.
---

# Codex Hook Doctor

This is the Codex-specific module nested under the main `hook-doctor` Skill.
Read and apply `../SKILL.md` first. The main Skill owns
host selection, generic installation and repair, the shared status model, and
cross-host reporting. This Skill owns only Codex-native discovery, trust, and
runtime evidence.

Map Codex evidence onto the shared model as follows:

- `enabled`: the owned `hooks/list` entry has `enabled=true`.
- `trusted`: `trustStatus` is `trusted` or `managed`.
- `invoked`: Codex started the installed command and the current installation produced status/trace evidence.
- `captured`: a Codex trace and project learning row contain the same invocation ID.

Do not infer `configured` or `selected` solely from app-server output; those
remain manager-owned states from the main Skill.

## Inspect

Run the bundled read-only diagnostic first:

```powershell
& "<configured Forge Python>" "<this-skill>\scripts\inspect_codex_hook.py" --project "<project-root>"
```

Locate the configured interpreter from `<forge-installation>\forge-data\runtime.json`. Prefer the logical installed Skill path under the active Codex home; do not assume a fixed drive or username. Pass `--forge-root` only when automatic discovery cannot identify the active Forge installation.

The script returns JSON with `layers`, the latest project-attributable trace,
the latest learning record, and an `assessment`:

Codex-native layer values are `true` or `false` only when the corresponding
evidence is observable. `enabled` and `trusted` are `null` when `hooks/list`
does not return the owned Hook, omits the required native field, or returns an
unknown field value. `invoked` and current `captured` are `null` when project
identity or the active installation baseline cannot be verified. Historical
`capturedPreviously` is also `null` when project identity is unverified.

- `CAPTURED`: all runtime evidence needed for a successful Skill capture exists.
- `HOOK_IN_PROGRESS`: the latest project-attributable trace has started but has not reached `hook_finished`.
- `HOST_NOT_SELECTED`: the Codex entry may exist, but Forge currently selects another global Hook host.
- `PREVIOUSLY_CAPTURED`: an earlier correlated capture exists, but the latest Hook trace did not capture that invocation (for example, an ordinary later turn returned `NO_PENDING_INVOCATION`).
- `CAPTURE_EVIDENCE_MISMATCH`: the latest trace says `CAPTURED`, but its invocation IDs do not match the latest captured learning row; treat this as inconsistent evidence, not success.
- `ACTIVE_NO_MATCH`: the Hook ran but no pending enabled Skill invocation matched. This is expected for ordinary greetings and unrelated turns.
- `TRUST_REQUIRED`: the current Hook hash is new, modified, or untrusted.
- `DISABLED`: Codex discovered the Hook but did not enable it.
- `NOT_CONFIGURED`: Forge's expected user Hook entry is absent or drifted.
- `NEVER_INVOKED`: configuration is ready, but the current installation has no trace attributable to this project.
- `HOOK_ERROR`: the latest current-installation trace attributable to this project reports failure.
- `STATUS_UNKNOWN`: Codex did not return the owned Hook or `hooks/list` failed.

`STATUS_UNKNOWN` also applies when Codex omits or returns an unknown native
enabled/trust value, when the project identity cannot be validated against
Forge's registry, or when the active Hook installation has no valid
`installedAt`. It also applies when Forge's Hook manager state or relevant
learning databases cannot be read reliably and a current correlated capture
cannot otherwise be proven. Inspect `forge.managerError`, `runtime.stateError`,
`runtime.traceError`, and `learning.errors` for bounded structured diagnostics. Do not treat old
trace or learning evidence as current in these cases. Codex historical capture
evidence must come from a learning row whose `hook_host` is `codex`.

Never manually execute `host_capture_hook.py` to prove success. That creates synthetic runtime evidence and does not verify Codex Desktop.

## Trust

If `trustStatus` is `untrusted` or `modified`, tell the user to open **Codex Desktop -> Settings -> Hooks**, review the exact user Hook, and select **Trust**. Trust is hash-bound; any command change requires review again. Start a new Codex session after trusting so the session loads the current Hook configuration.

Do not use `--dangerously-bypass-hook-trust` as a permanent fix. It is acceptable only as an explicitly requested one-run diagnostic.

This trust workflow is verified only for Codex. The main `hook-doctor` Skill
owns the cross-host boundary: Claude Code and Cursor trust remain `UNVERIFIED`
until their native contracts are independently established.

## End-To-End Verification

To verify capture rather than mere invocation:

1. Confirm the target project enables a Forge Skill in `.forge-skill/learning/config.json`.
2. Start a new Codex session in that project.
3. Invoke an enabled Skill, such as `code review` when `code-review` is enabled.
4. Wait for the final response and native `Stop` completion.
5. Rerun the diagnostic and correlate one invocation ID across `invocation_match`, `collection_finished` with `stored=true`, `hook_finished` with `outcome=CAPTURED`, the learning row with `hook_status=CAPTURED`, and removal of the pending marker.

`SKILL_CONTRACT` plus `hook_status=CAPTURED` is the expected merged result: the Skill's structured fallback remains canonical, while the native Hook adds host-response evidence. It is not duplicate collection. Top-level `CAPTURED` additionally requires that the latest trace belongs to the requested project, comes from the current Hook installation, has `outcome=CAPTURED`, and contains the same invocation ID as the captured learning row. A later unrelated `NO_PENDING_INVOCATION` does not invalidate historical success; the diagnostic reports `capturedPreviously=true` and `PREVIOUSLY_CAPTURED` instead of claiming that the latest Hook run captured data.

## Reporting

Report all six shared dimensions explicitly: `configured`, `selected`,
`enabled`, `trusted`, `invoked`, and `captured`. Also report
`capturedPreviously`, the latest invocation ID, and timestamps when present.
Distinguish observed facts from next-step instructions. A `hook/started` or
`hook/completed` app-server event alone is insufficient because it does not
prove that the configured command entered the Python handler or persisted a
result.
