#!/usr/bin/env python3
"""Receive one native host Hook event without blocking the host task."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Callable, ContextManager


MAX_INPUT_BYTES = 4_000_000
TRACE_MAX_BYTES = 1_000_000
TRACE_RETAIN_BYTES = 750_000
TRACE_LOCK_TIMEOUT_SECONDS = 0.25
_TRACE_LOCK = threading.Lock()


def _status_path(forge_root: Path, host: str) -> Path:
    configured = os.getenv("FORGE_DATA_ROOT")
    root = Path(configured).expanduser().resolve(strict=False) if configured else (
        forge_root.absolute().parent / "forge-data"
    )
    return root / "hook-status" / f"{host}.json"


def _trace_path(forge_root: Path, host: str) -> Path:
    return _status_path(forge_root, host).with_suffix(".trace.jsonl")


def _write_trace(
    forge_root: Path,
    host: str,
    trace_id: str,
    step: str,
    *,
    file_lock: Callable[[Path], ContextManager[None]] | None = None,
    **fields: object,
) -> bool:
    """Append one bounded, content-free diagnostic event without blocking the Hook."""
    value = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "traceId": trace_id,
        "host": host,
        "step": step,
        **fields,
    }
    path = _trace_path(forge_root, host)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        lock = file_lock(path) if file_lock is not None else nullcontext()
        with _TRACE_LOCK, lock:
            with path.open("ab") as handle:
                handle.write(line)
                handle.flush()
            if path.stat().st_size <= TRACE_MAX_BYTES:
                return True
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - TRACE_RETAIN_BYTES))
                retained = handle.read()
            if len(retained) == TRACE_RETAIN_BYTES:
                _, separator, retained = retained.partition(b"\n")
                if not separator:
                    retained = line
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(retained)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        return True
    except Exception:
        return False


def _write_status(
    forge_root: Path,
    host: str,
    event: str,
    outcome: str,
    *,
    detail: str | None = None,
    error_type: str | None = None,
) -> None:
    """Persist bounded diagnostics without exposing event content."""
    value = {
        "schemaVersion": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": host,
        "event": event,
        "outcome": outcome,
        "detail": detail[:240] if isinstance(detail, str) else None,
        "errorType": error_type,
        "interpreterPath": sys.executable,
    }
    path = _status_path(forge_root, host)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude-code", "cursor"), required=True)
    parser.add_argument("--event", choices=("after-agent-response", "stop"), required=True)
    parser.add_argument("--forge-hook-marker", required=True)
    parser.add_argument("--forge-root", type=Path, required=True)
    args = parser.parse_args()
    trace_id = uuid.uuid4().hex
    sys.path.insert(0, str(args.forge_root.resolve()))
    try:
        from forge_cli.learning_collector import _registry_file_lock
    except (ImportError, OSError):
        trace_file_lock = None
    else:
        trace_file_lock = partial(
            _registry_file_lock, timeout=TRACE_LOCK_TIMEOUT_SECONDS
        )

    trace_enabled = True

    def trace(step: str, **fields: object) -> None:
        nonlocal trace_enabled
        if trace_enabled:
            trace_enabled = _write_trace(
                args.forge_root, args.host, trace_id, step,
                file_lock=trace_file_lock, **fields,
            )

    trace("hook_invoked", event=args.event, pid=os.getpid())
    if args.forge_hook_marker != "forge-learning-capture-v1":
        trace("hook_finished", outcome="FAILED", reason="InvalidMarker")
        _write_status(args.forge_root, args.host, args.event, "FAILED", error_type="InvalidMarker")
        print("{}")
        return
    _write_status(args.forge_root, args.host, args.event, "INVOKED")
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    trace("input_received", bytesRead=len(raw), withinLimit=len(raw) <= MAX_INPUT_BYTES)
    if not raw.strip() or len(raw) > MAX_INPUT_BYTES:
        reason = "InputTooLarge" if len(raw) > MAX_INPUT_BYTES else "EmptyInput"
        trace("hook_finished", outcome="SKIPPED", reason=reason)
        _write_status(args.forge_root, args.host, args.event, "SKIPPED", detail=reason)
        print("{}")
        return
    try:
        payload = json.loads(raw.decode("utf-8-sig", errors="strict"))
        if not isinstance(payload, dict):
            raise ValueError("Hook input must be an object")
        trace("payload_decoded", hasCwd=isinstance(payload.get("cwd"), str),
              hasWorkspaceRoots=isinstance(payload.get("workspace_roots"), list),
              hasFinalMessage=bool(payload.get("last_assistant_message")),
              identityFields=[key for key in ("session_id", "turn_id") if payload.get(key)])
        from forge_cli.learning_invocations import handle_host_event

        result = handle_host_event(args.forge_root.resolve(), args.host, args.event, payload, trace=trace)
        outcome = "CAPTURED" if result.get("action") == "CAPTURED" else (
            "HANDLED" if result.get("handled") else "SKIPPED"
        )
        detail = result.get("action") or result.get("reason")
        trace("hook_finished", outcome=outcome, reason=detail,
              matchedCount=len(result.get("invocationIds", [])))
        _write_status(args.forge_root, args.host, args.event, outcome, detail=detail)
    except Exception as error:
        trace("hook_finished", outcome="FAILED", errorType=type(error).__name__)
        _write_status(
            args.forge_root, args.host, args.event, "FAILED", error_type=type(error).__name__
        )
    print("{}")


if __name__ == "__main__":
    main()
