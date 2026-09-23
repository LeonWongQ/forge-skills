---
name: hook-doctor
description: >-
  Primary entry point for installing, inspecting, repairing, and verifying the
  user-global Forge learning Hook across Codex, Claude Code, and Cursor. Use
  for general Hook health questions, unknown-host diagnosis, host switching,
  or end-to-end Skill capture checks; load the matching host-specific doctor
  for native trust and protocol details.
---

# Hook Doctor

Load `.forge-skill/forge/CLAUDE.md` and `.forge-skill/forge/AUTOLOAD.md` at
activation, including the shared direct-host learning lifecycle.

Use this Skill as the main entry point for Forge learning Hook work. It owns
the shared lifecycle, host selection, common status language, and mutation
boundaries. Host-specific doctors add native evidence; they do not redefine
the shared success criteria.

## Shared Status Model

Report these dimensions independently:

1. `configured`: Forge owns the expected user-global Hook entry.
2. `selected`: this host is the single host currently selected by Forge.
3. `enabled`: the host reports the Hook enabled, when that state is observable.
4. `trusted`: the host-specific trust result, or `UNVERIFIED` when no verified trust contract exists.
5. `invoked`: an event from the current installation reached the Hook runtime.
6. `captured`: one Hook trace and one learning row correlate to the same invocation ID.

Do not collapse unknown, unsupported, or unverified states into `false`.
Configuration does not prove invocation, and invocation does not prove capture.
Historical capture evidence must be reported separately from the latest Hook
outcome.

## Inspect

Locate the configured interpreter and installation root from the active
`forge-data/runtime.json`. Run the existing manager read-only status command:

```powershell
& "<configured Forge Python>" "<learning-collector>\scripts\manage_host_hook.py" status
```

Use `selectedHost`, per-host `configState`, `runtimeState`, `lastEvent`, and
`detail` as the generic evidence. `runtimeState=NEVER_OBSERVED` means the
current installation has not been observed even if an older status file or
learning record exists.

After identifying the host, load only its specialized guidance:

- Codex: read `codex-hook-doctor/SKILL.md` inside this Skill and use its bundled diagnostic.
- Claude Code: read `claude-code-hook-doctor/SKILL.md` inside this Skill for
  native settings, transcript, shell, payload, and runtime evidence. Its trust
  model is currently unverified.
- Cursor: inspect the manager result and native configuration only. Its trust model is currently unverified.

Do not apply Codex trust hashes, `trustStatus`, Desktop UI, or bypass flags to
Claude Code or Cursor.

## Install, Switch, Or Repair

Configuration is an explicit mutation. Perform it only when the user asks to
install, switch, or repair the Hook:

```powershell
& "<configured Forge Python>" "<learning-collector>\scripts\manage_host_hook.py" configure --host <codex|claude-code|cursor>
```

Forge supports one selected global Hook host. Switching hosts removes Forge's
owned entry from the previous host. Preserve unrelated user Hooks and never
edit native trust persistence directly.

Removal also requires an explicit request:

```powershell
& "<configured Forge Python>" "<learning-collector>\scripts\manage_host_hook.py" remove
```

## End-To-End Verification

1. Confirm the project enables the target Skill in `.forge-skill/learning/config.json`.
2. Start a new host session when the host requires configuration reload.
3. Invoke an enabled Skill and retain its invocation ID.
4. Let the native completion event finish.
5. Correlate that invocation ID across the host trace and the project learning row.

Use these common outcomes:

- `CAPTURED`: the latest relevant trace and learning row correlate.
- `PREVIOUSLY_CAPTURED`: historical correlated success exists, but the latest relevant event did not capture.
- `ACTIVE_NO_MATCH`: the Hook ran, but no pending enabled Skill invocation matched.
- `NEVER_INVOKED`: the current installation has not produced an attributable event.
- `HOOK_ERROR`: the latest attributable runtime event failed.
- `STATUS_UNKNOWN`: the host-specific state could not be read reliably.

These names are the canonical cross-host outcome vocabulary. Host-specific
modules must use them directly rather than adding a host prefix.

Never execute a Hook handler manually to manufacture native evidence.

## Reporting

Name the selected host, report every shared dimension, and identify which
states came from generic Forge evidence versus a host-specific doctor. Include
invocation IDs and timestamps when available. State explicitly when trust or
enabled state is `UNVERIFIED` instead of guessing.
