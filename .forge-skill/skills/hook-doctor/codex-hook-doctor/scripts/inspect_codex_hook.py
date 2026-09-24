#!/usr/bin/env python3
"""Read-only end-to-end status inspection for the Forge Codex learning Hook."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import json
import os
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


PROJECT_ID_PATTERN = re.compile(
    r"^project-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
TRACE_TAIL_BYTES = 512_000
TRACE_TAIL_LINES = 500


def _error_detail(error: BaseException) -> dict[str, str]:
    return {"errorType": type(error).__name__, "message": str(error)[:240]}


def _forge_root(explicit: Path | None, project: Path) -> Path:
    candidates = [explicit, project / ".forge-skill" / "forge", project / ".codex" / "forge",
                  Path(__file__).resolve().parents[4] / "forge"]
    if os.getenv("CODEX_HOME"):
        candidates.append(Path(os.environ["CODEX_HOME"]).expanduser() / "forge")
    candidates.append(Path.home() / ".codex" / "forge")
    for candidate in candidates:
        if candidate is not None and (candidate / "forge_cli").is_dir():
            return candidate.resolve()
    raise SystemExit("cannot locate the active Forge root; pass --forge-root")


def _codex_executable(explicit: Path | None) -> Path | None:
    if explicit and explicit.is_file():
        return explicit.resolve()
    found = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if found:
        return Path(found).resolve()
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        matches = sorted(root.glob("*/codex.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
        if matches:
            return matches[0].resolve()
    return None


def _read_stdout(process: subprocess.Popen[str], messages: queue.Queue[tuple[str, Any]]) -> None:
    """Forward one process stdout stream into one queue for its full lifetime."""
    if process.stdout is None:
        messages.put(("error", "app-server stdout is unavailable"))
        return
    try:
        while True:
            line = process.stdout.readline()
            if line == "":
                messages.put(("eof", process.poll()))
                return
            messages.put(("line", line))
    except Exception as error:
        messages.put(("error", f"app-server stdout read failed: {error}"))


def _hooks_list(
    executable: Path | None, project: Path, timeout: float = 5.0
) -> tuple[dict[str, Any] | None, str | None]:
    if executable is None:
        return None, "codex executable not found"
    try:
        process = subprocess.Popen(
            [str(executable), "app-server", "--stdio"], cwd=project,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8",
        )
    except OSError as error:
        return None, f"app-server launch failed: {error}"
    reader: threading.Thread | None = None
    try:
        messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        reader = threading.Thread(target=_read_stdout, args=(process, messages), daemon=True)
        reader.start()
        requests = (
            {"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "codex-hook-doctor", "version": "1.0"}, "capabilities": {}}},
            {"method": "initialized", "params": {}},
            {"id": 2, "method": "hooks/list", "params": {}},
        )
        assert process.stdin is not None
        for request in requests:
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, "hooks/list timed out or returned no result"
            try:
                kind, value = messages.get(timeout=remaining)
            except queue.Empty:
                return None, "hooks/list timed out or returned no result"
            if kind == "error":
                return None, str(value)
            if kind == "eof":
                suffix = f" with exit code {value}" if value is not None else ""
                return None, f"app-server exited before hooks/list response{suffix}"
            try:
                message = json.loads(value)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("id") != 2:
                continue
            if "error" in message:
                return None, str(message["error"])
            result = message.get("result")
            if not isinstance(result, dict):
                return None, "hooks/list returned an invalid result object"
            entries = result.get("data")
            if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
                return None, "hooks/list returned invalid data entries"
            target = project.resolve(strict=False)
            matching = []
            for item in entries:
                cwd = item.get("cwd")
                if not isinstance(cwd, str) or not cwd.strip():
                    continue
                try:
                    candidate = Path(cwd).resolve(strict=False)
                except OSError:
                    continue
                if candidate == target:
                    matching.append(item)
            selected = matching[0] if matching else None
            if selected is None and len(entries) == 1 and not str(
                entries[0].get("cwd", "")
            ).strip():
                selected = entries[0]
            if selected is None:
                return None, "hooks/list returned no entry for the requested project"
            hooks = selected.get("hooks")
            if not isinstance(hooks, list) or not all(isinstance(hook, dict) for hook in hooks):
                return None, "hooks/list returned invalid hooks entries"
            return selected, None
    except OSError as error:
        return None, f"app-server communication failed: {error}"
    finally:
        try:
            if process.poll() is None:
                process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if reader is not None:
            reader.join(timeout=1)


def _latest_trace(
    path: Path, project_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - TRACE_TAIL_BYTES)
            handle.seek(start)
            content = handle.read()
    except FileNotFoundError:
        return None, None
    except OSError as error:
        return None, {"path": str(path), "errorType": type(error).__name__}
    if start:
        _, separator, content = content.partition(b"\n")
        if not separator:
            return None, {"path": str(path), "errorType": "InvalidTrace"}
    lines = content.splitlines()[-TRACE_TAIL_LINES:]
    events = []
    invalid_lines = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid_lines += 1
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            invalid_lines += 1
    if not events:
        error = (
            {"path": str(path), "errorType": "InvalidTrace"}
            if invalid_lines else None
        )
        return None, error
    trace_ids = list(dict.fromkeys(
        event.get("traceId") for event in reversed(events)
        if isinstance(event.get("traceId"), str)
    ))
    selected = []
    trace_id = None
    for candidate in trace_ids:
        candidate_events = [event for event in events if event.get("traceId") == candidate]
        resolution = next(
            (event for event in candidate_events if event.get("step") == "project_resolution"),
            None,
        )
        if project_id is not None and (
            not isinstance(resolution, dict) or resolution.get("projectId") != project_id
        ):
            continue
        trace_id = candidate
        selected = candidate_events
        break
    if not selected:
        return None, None
    finished = next((event for event in reversed(selected) if event.get("step") == "hook_finished"), {})
    match = next((event for event in selected if event.get("step") == "invocation_match"), {})
    return ({"traceId": trace_id, "timestamp": selected[-1].get("timestamp"),
             "projectId": project_id,
             "steps": [event.get("step") for event in selected],
             "invocationIds": match.get("invocationIds", []),
             "outcome": finished.get("outcome"), "reason": finished.get("reason"),
             "complete": bool(finished)}, None)


def _project_id(forge_root: Path, project: Path) -> str | None:
    try:
        identity = json.loads(
            (project / ".forge-skill" / "learning" / "project.json").read_text(encoding="utf-8")
        )
        registry = json.loads(
            (forge_root.parent / "forge-data" / "project-registry.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    project_id = identity.get("projectId") if isinstance(identity, dict) else None
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id):
        return None
    entries = registry.get("projects") if isinstance(registry, dict) else None
    if not isinstance(entries, list):
        return None
    entry = next((item for item in entries if isinstance(item, dict)
                  and item.get("projectId", item.get("id")) == project_id), None)
    registered_path = entry.get("path") if isinstance(entry, dict) else None
    if not isinstance(registered_path, str) or not registered_path.strip():
        return None
    try:
        if Path(registered_path).resolve(strict=False) != project.resolve(strict=False):
            return None
    except OSError:
        return None
    return project_id


def _at_or_after_installation(
    trace: dict[str, Any] | None, installed_at: Any
) -> bool | None:
    installed = _aware_datetime(installed_at)
    if installed is None:
        return None
    if trace is None:
        return False
    observed = _aware_datetime(trace.get("timestamp"))
    if observed is None:
        return None
    return observed >= installed


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]", value):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
    except (TypeError, ValueError):
        return None
    return parsed


def _latest_records(
    forge_root: Path, project: Path, project_id: str | None = None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, str]]]:
    project_id = project_id or _project_id(forge_root, project)
    if project_id is None:
        return None, None, []
    projects_root = (forge_root.parent / "forge-data" / "projects").resolve(strict=False)
    root = (projects_root / project_id / "learning").resolve(strict=False)
    if root != projects_root / project_id / "learning":
        return None, None, []
    records = []
    captured_records = []
    errors = []
    try:
        databases = list(root.glob("*/learning.sqlite"))
    except OSError as error:
        return None, None, [{"database": str(root), "errorType": type(error).__name__}]
    for database in databases:
        try:
            with closing(sqlite3.connect(
                f"file:{database.as_posix()}?mode=ro", uri=True
            )) as connection:
                connection.row_factory = sqlite3.Row
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(learning_records)")
                }
                if not {"skill", "captured_at"}.issubset(columns):
                    raise sqlite3.OperationalError(
                        "learning_records is missing required diagnostic columns"
                    )
                invocation_id = "invocation_id" if "invocation_id" in columns else "NULL"
                capture_source = (
                    "capture_source" if "capture_source" in columns else "'RUNTIME'"
                )
                hook_host = "hook_host" if "hook_host" in columns else "NULL"
                hook_status = (
                    "hook_status" if "hook_status" in columns else "'NOT_EXPECTED'"
                )
                hook_captured_at = (
                    "hook_captured_at" if "hook_captured_at" in columns else "NULL"
                )
                latest = connection.execute(
                    f"SELECT {invocation_id} AS invocation_id, skill, "
                    f"{capture_source} AS capture_source, {hook_host} AS hook_host, "
                    f"{hook_status} AS hook_status, captured_at, "
                    f"{hook_captured_at} AS hook_captured_at FROM learning_records "
                    "ORDER BY captured_at DESC LIMIT 1"
                ).fetchone()
                captured = None
                if {"hook_status", "hook_host"}.issubset(columns):
                    captured = connection.execute(
                        f"SELECT {invocation_id} AS invocation_id, skill, "
                        f"{capture_source} AS capture_source, hook_host, hook_status, "
                        f"captured_at, {hook_captured_at} AS hook_captured_at "
                        "FROM learning_records "
                        "WHERE hook_status = 'CAPTURED' AND hook_host = 'codex' "
                        f"ORDER BY COALESCE({hook_captured_at}, captured_at) DESC LIMIT 1"
                    ).fetchone()
        except (OSError, sqlite3.Error) as error:
            errors.append({"database": str(database), "errorType": type(error).__name__})
            continue
        if latest is not None:
            records.append(dict(latest))
        if captured is not None:
            captured_records.append(dict(captured))
    latest_record = max(records, key=lambda item: item.get("captured_at") or "") if records else None
    latest_captured = max(
        captured_records,
        key=lambda item: item.get("hook_captured_at") or item.get("captured_at") or "",
    ) if captured_records else None
    return latest_record, latest_captured, errors


def _capture_layers(
    trace: dict[str, Any] | None, captured_record: dict[str, Any] | None,
    current_installation_observed: bool | None = True,
    *, identity_verified: bool = True,
) -> dict[str, bool | None]:
    if not identity_verified:
        return {"captured": None, "capturedPreviously": None}
    captured_previously = bool(
        captured_record and captured_record.get("hook_status") == "CAPTURED"
    )
    invocation_id = captured_record.get("invocation_id") if captured_record else None
    trace_ids = trace.get("invocationIds", []) if trace else []
    captured = None if current_installation_observed is None else bool(
        captured_previously
        and current_installation_observed
        and invocation_id
        and trace
        and trace.get("outcome") == "CAPTURED"
        and invocation_id in trace_ids
    )
    return {"captured": captured, "capturedPreviously": captured_previously}


def _native_hook_layers(
    owned: dict[str, Any] | None,
) -> tuple[bool | None, bool | None]:
    if owned is None:
        return None, None
    enabled_value = owned.get("enabled")
    enabled = enabled_value if isinstance(enabled_value, bool) else None
    trust_status = owned.get("trustStatus")
    if trust_status in {"trusted", "managed"}:
        trusted = True
    elif trust_status in {"untrusted", "modified"}:
        trusted = False
    else:
        trusted = None
    return enabled, trusted


def _assessment(
    layers: dict[str, bool | None], owned: dict[str, Any] | None,
    trace: dict[str, Any] | None,
    *, identity_verified: bool = True, installation_verified: bool = True,
    learning_verified: bool = True,
) -> str:
    if layers.get("configured") is None:
        return "STATUS_UNKNOWN"
    if layers["configured"] is False:
        return "NOT_CONFIGURED"
    if owned is None:
        return "STATUS_UNKNOWN"
    if not identity_verified or not installation_verified:
        return "STATUS_UNKNOWN"
    if layers["enabled"] is None or layers["trusted"] is None:
        return "STATUS_UNKNOWN"
    if layers["enabled"] is False:
        return "DISABLED"
    if layers["trusted"] is False:
        return "TRUST_REQUIRED"
    if layers["invoked"] is None:
        return "STATUS_UNKNOWN"
    if layers["invoked"] is False:
        return "NEVER_INVOKED"
    if trace and trace.get("outcome") == "FAILED":
        return "HOOK_ERROR"
    if trace and not trace.get("complete", True):
        return "HOOK_IN_PROGRESS"
    if layers["captured"]:
        return "CAPTURED"
    if not learning_verified:
        return "STATUS_UNKNOWN"
    if trace and trace.get("outcome") == "CAPTURED":
        return "CAPTURE_EVIDENCE_MISMATCH"
    if layers["capturedPreviously"]:
        return "PREVIOUSLY_CAPTURED"
    return "ACTIVE_NO_MATCH"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--forge-root", type=Path)
    parser.add_argument("--codex-executable", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    forge_root = _forge_root(args.forge_root, project)
    sys.path.insert(0, str(forge_root))
    from forge_cli.learning_hook_manager import (
        global_hook_status,
        hook_event_status_path,
        load_hook_state,
    )

    manager = None
    manager_error = None
    try:
        manager = global_hook_status(forge_root)
    except (OSError, ValueError) as error:
        manager_error = _error_detail(error)
    hook_group, hooks_error = _hooks_list(_codex_executable(args.codex_executable), project)
    hooks = hook_group.get("hooks", []) if isinstance(hook_group, dict) else []
    owned = next((hook for hook in hooks if hook.get("source") == "user"
                  and hook.get("eventName") == "stop"
                  and "forge-learning-capture-v1" in str(hook.get("command", ""))), None)
    status_path = hook_event_status_path(forge_root, "codex")
    try:
        native_status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        native_status = None
    project_id = _project_id(forge_root, project)
    trace, trace_error = (
        _latest_trace(status_path.with_suffix(".trace.jsonl"), project_id)
        if project_id is not None else (None, None)
    )
    record, captured_record, learning_errors = _latest_records(
        forge_root, project, project_id
    )
    codex_state = (
        manager.get("hosts", {}).get("codex") if isinstance(manager, dict) else None
    )
    hook_state = None
    state_error = None
    try:
        hook_state = load_hook_state(forge_root)
    except (OSError, ValueError) as error:
        state_error = _error_detail(error)
    host_state = (
        hook_state.get("hosts", {}).get("codex", {})
        if isinstance(hook_state, dict) else {}
    )
    installed_at = host_state.get("installedAt") if isinstance(host_state, dict) else None
    installation_relation = (
        _at_or_after_installation(trace, installed_at)
        if project_id is not None and trace_error is None else None
    )
    invoked = installation_relation
    capture_layers = _capture_layers(
        trace, captured_record, installation_relation,
        identity_verified=project_id is not None,
    )
    enabled, trusted = _native_hook_layers(owned)
    configured = (
        codex_state.get("configState") == "CONFIGURED"
        if isinstance(codex_state, dict) and isinstance(codex_state.get("configState"), str)
        else None
    )
    layers = {
        "configured": configured,
        "enabled": enabled,
        "trusted": trusted,
        "invoked": invoked,
        **capture_layers,
    }
    assessment = _assessment(
        layers, owned, trace,
        identity_verified=project_id is not None,
        installation_verified=installation_relation is not None,
        learning_verified=not learning_errors,
    )
    print(json.dumps({
        "schemaVersion": "2.0", "assessment": assessment, "layers": layers,
        "forge": {"root": str(forge_root), "manager": codex_state,
                  "managerError": manager_error},
        "codex": {"hook": owned, "warnings": hook_group.get("warnings", []) if hook_group else [],
                  "error": hooks_error},
        "runtime": {"statusPath": str(status_path), "lastStatus": native_status,
                    "installedAt": installed_at, "latestTrace": trace,
                    "traceFromCurrentInstallation": installation_relation,
                    "stateError": state_error, "traceError": trace_error},
        "learning": {"latestRecord": record, "latestCapturedRecord": captured_record,
                     "errors": learning_errors},
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
