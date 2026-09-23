---
name: claude-code-hook-doctor
description: >-
  Claude Code-specific extension for the main hook-doctor Skill. Use for
  Claude user and project Hook settings, Stop transcript errors, Windows shell
  command behavior, session identity, and Claude-native capture evidence.
  Use hook-doctor as the primary shared workflow.
---

# Claude Code Hook Doctor

Read and apply `../SKILL.md` first. The main Skill owns host selection,
installation, the shared status model, and cross-host capture criteria. This
module owns only Claude Code-native evidence and failure modes.

## Native Evidence

Inspect these layers without treating configuration as runtime proof:

1. Manager status for `configured`, `selected`, `runtimeState`, and `lastEvent`.
2. User settings at `~/.claude/settings.json` and project overrides at
   `.claude/settings.json` and `.claude/settings.local.json`.
3. The matching session transcript under `~/.claude/projects/` for
   `hook_non_blocking_error`, `stop_hook_summary`, the executed command, exit
   code, and stderr.
4. Forge's `claude-code.trace.jsonl`, status file, pending marker, and learning
   row correlated by one invocation ID.

Report `enabled` only when Claude runtime or transcript evidence proves that
the configured Stop Hook was active. Report `trusted=UNVERIFIED`; do not apply
Codex trust hashes, Trust UI, or bypass flags to Claude Code.

## Windows Commands

Claude Code's Windows Hook runner parses command text with POSIX-style shell
semantics. Forge commands must use forward-slash paths and POSIX-safe quoting.
An error path such as `E:\CodexHomeskills...` means unquoted backslashes were
consumed before Python started. In that case, repair through the main manager
and start a new Claude session; do not edit only the persisted manager state.

After a command change, require a fresh native trace from at or after the new
`installedAt`. A parser-only test or an older successful trace is not current
runtime proof.

## Stop Correlation

Claude Stop payloads provide `session_id`, `cwd`, and
`last_assistant_message`; do not assume a usable `turn_id`. Direct invocation
markers should bind `CLAUDE_CODE_SESSION_ID` when available. Session identity
separates different Claude sessions but cannot distinguish concurrent pending
turns in the same session. Preserve `AMBIGUOUS_INVOCATION` rather than guessing.

The direct begin call must identify `claude-code` as the current host. If a
Skill is executing in Codex or Cursor while Claude is merely the selected Hook
host, it must not create a Claude pending marker.

## End-To-End Result

Use the main Skill's canonical outcomes. Report `CAPTURED` only when the same
invocation ID appears in a current Claude trace with `collection_finished`
`stored=true` and `hook_finished` `outcome=CAPTURED`, and in a learning row
with `hook_host=claude-code` and `hook_status=CAPTURED`.

A later `NO_PENDING_INVOCATION` is `ACTIVE_NO_MATCH` for that event and does
not erase an earlier correlated capture. A transcript-level nonzero exit is
`HOOK_ERROR` even when no Forge trace exists, because the process may have
failed before entering Python.

Never execute `host_capture_hook.py` manually to manufacture native evidence.
