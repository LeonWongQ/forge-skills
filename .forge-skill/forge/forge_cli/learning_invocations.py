"""Correlate direct Skill fallbacks with native host completion Hooks."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .data_paths import project_data_root
from .learning_collector import (
    _load_enabled_skills,
    _project_database,
    _registry_file_lock,
    collect_imported_result,
    connect_database,
    has_meaningful_content,
)
from .learning_hook_manager import global_hook_selection
from .personal_hook_state import _atomic_write, _json_bytes
from .runtime_paths import _project_id


INVOCATION_TTL_HOURS = 6
_INVOCATION_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _invocation_directory(forge_root: Path, project_id: str) -> Path:
    return project_data_root(forge_root, project_id) / "learning" / "invocations"


def _load_marker(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_marker(path: Path, marker: dict[str, Any]) -> None:
    _atomic_write(path, _json_bytes(marker))


def _text_identity(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _host_identity(host: str, payload: dict[str, Any]) -> dict[str, str]:
    """Keep only stable host-provided identity fields used for correlation."""
    if host == "cursor":
        values = {
            "conversationId": _text_identity(payload.get("conversation_id")),
            "generationId": _text_identity(payload.get("generation_id")),
        }
    else:
        values = {
            "sessionId": _text_identity(payload.get("session_id")),
            "turnId": _text_identity(payload.get("turn_id")),
        }
    return {key: value for key, value in values.items() if value is not None}


def _identity_is_complete(host: str, identity: dict[str, str]) -> bool:
    if host == "cursor":
        return set(identity) == {"conversationId", "generationId"}
    return True


def _identity_is_turn_unique(host: str, identity: dict[str, str]) -> bool:
    if host == "cursor":
        return _identity_is_complete(host, identity)
    return "turnId" in identity


def _ambient_host_identity(host: str) -> dict[str, str]:
    """Use optional host environment identity without making it a requirement."""
    if host == "codex":
        session_id = os.getenv("CODEX_SESSION_ID") or os.getenv("CODEX_THREAD_ID")
        return {"sessionId": session_id.strip()} if session_id and session_id.strip() else {}
    if host == "claude-code":
        session_id = os.getenv("CLAUDE_SESSION_ID")
        return {"sessionId": session_id.strip()} if session_id and session_id.strip() else {}
    if host == "cursor":
        conversation_id = os.getenv("CURSOR_CONVERSATION_ID")
        generation_id = os.getenv("CURSOR_GENERATION_ID")
        return {
            key: value.strip()
            for key, value in {
                "conversationId": conversation_id,
                "generationId": generation_id,
            }.items()
            if value and value.strip()
        }
    return {}


def _identity_matches(marker: dict[str, Any], identity: dict[str, str]) -> bool:
    stored = marker.get("hostIdentity")
    return (
        isinstance(stored, dict)
        and bool(stored)
        and all(identity.get(key) == value for key, value in stored.items())
    )


def _select_pending(
    host: str,
    pending: list[tuple[Path, dict[str, Any]]],
    identity: dict[str, str],
) -> list[tuple[Path, dict[str, Any]]]:
    turn_unique = _identity_is_turn_unique(host, identity)
    # A session can contain multiple turns. Never batch-select session-only
    # markers when the host gives us a turn-level identity.
    exact = [
        item for item in pending
        if _identity_matches(item[1], identity)
        and (not turn_unique or host == "cursor"
             or "turnId" in (item[1].get("hostIdentity") or {}))
    ]
    if exact:
        return exact if len(exact) == 1 or turn_unique else []
    if turn_unique:
        session_only = [
            item for item in pending
            if _identity_matches(item[1], identity)
            and "turnId" not in (item[1].get("hostIdentity") or {})
        ]
        if len(session_only) > 1:
            return []
        if len(session_only) == 1:
            path, marker = session_only[0]
            stored_session = (marker.get("hostIdentity") or {}).get("sessionId")
            conflicting = [
                item for item in pending
                if item != (path, marker)
                and stored_session
                and (item[1].get("hostIdentity") or {}).get("sessionId") == stored_session
            ]
            if conflicting:
                return []
            marker["hostIdentity"] = identity
            _write_marker(path, marker)
            return [(path, marker)]
    unbound = [item for item in pending if not item[1].get("hostIdentity")]
    if len(unbound) != 1:
        return []
    path, marker = unbound[0]
    if identity:
        marker["hostIdentity"] = identity
        _write_marker(path, marker)
    return [(path, marker)]


def begin_invocation(
    forge_root: Path,
    project: Path,
    skill: str,
    *,
    hook_home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    """Create one correlation marker only when native Hook capture is selected."""
    project = project.resolve()
    normalized = skill.removeprefix("skill.").replace("_", "-")
    enabled = _load_enabled_skills(forge_root, project)
    if enabled is None or normalized not in enabled or normalized == "learning-collector":
        return {"started": False, "reason": "SKILL_NOT_ENABLED"}
    project_id = _project_id(forge_root, project)
    host = global_hook_selection(forge_root, home=hook_home, codex_home=codex_home)
    invocation_id = f"inv-{uuid.uuid4()}"
    result = {
        "started": True,
        "invocationId": invocation_id,
        "projectId": project_id,
        "skill": normalized,
        "hookHost": host,
        "hookExpected": isinstance(host, str),
    }
    if not isinstance(host, str):
        return result
    directory = _invocation_directory(forge_root, project_id)
    directory.mkdir(parents=True, exist_ok=True)
    marker = {
        "schemaVersion": "2.0",
        "invocationId": invocation_id,
        "projectId": project_id,
        "projectPath": str(project),
        "skill": normalized,
        "host": host,
        "status": "PENDING",
        "startedAt": _timestamp(_now()),
        "expiresAt": _timestamp(_now() + timedelta(hours=INVOCATION_TTL_HOURS)),
    }
    identity = _ambient_host_identity(host)
    if identity:
        marker["hostIdentity"] = identity
    with _INVOCATION_LOCK, _registry_file_lock(directory / ".lock"):
        _purge_expired_markers(forge_root, directory)
        _write_marker(directory / f"{invocation_id}.json", marker)
    return result


def _mark_missed(forge_root: Path, marker: dict[str, Any]) -> None:
    project_id = marker.get("projectId")
    skill = marker.get("skill")
    invocation_id = marker.get("invocationId")
    if not all(isinstance(item, str) and item for item in (project_id, skill, invocation_id)):
        return
    database = _project_database(forge_root, project_id, skill)
    if not database.is_file():
        return
    connection = connect_database(database)
    try:
        with connection:
            connection.execute(
                "UPDATE learning_records SET hook_status = 'MISSED' "
                "WHERE invocation_id = ? AND reviewed = 0 AND hook_status = 'PENDING'",
                (invocation_id,),
            )
    finally:
        connection.close()


def _purge_expired_markers(forge_root: Path, directory: Path) -> None:
    now = _now()
    for path in directory.glob("inv-*.json"):
        marker = _load_marker(path)
        expires = _parse_timestamp(marker.get("expiresAt")) if marker else None
        if marker is None or expires is None or expires <= now:
            if marker is not None:
                _mark_missed(forge_root, marker)
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _project_root(candidate: Path) -> Path | None:
    candidate = candidate.resolve(strict=False)
    if candidate.is_file():
        candidate = candidate.parent
    for path in (candidate, *candidate.parents):
        if (path / ".forge-skill" / "learning" / "project.json").is_file():
            return path
    return None


def _project_from_payload(payload: dict[str, Any]) -> Path | None:
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        project = _project_root(Path(cwd))
        if project is not None:
            return project
    roots = payload.get("workspace_roots")
    if isinstance(roots, list):
        candidates = {
            project
            for item in roots
            if isinstance(item, str) and item.strip()
            for project in [_project_root(Path(item))]
            if project is not None
        }
        if len(candidates) == 1:
            return next(iter(candidates))
    return None


def _project_identity(project: Path) -> str | None:
    path = project / ".forge-skill" / "learning" / "project.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    project_id = value.get("projectId") if isinstance(value, dict) else None
    return project_id if isinstance(project_id, str) and project_id.startswith("project-") else None


def handle_host_event(
    forge_root: Path,
    host: str,
    event: str,
    payload: dict[str, Any],
    *,
    hook_home: Path | None = None,
    codex_home: Path | None = None,
    trace: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Buffer or finalize one safely attributable host response."""
    def note(step: str, **fields: object) -> None:
        if trace is not None:
            trace(step, **fields)

    note("handler_entered", method="handle_host_event", event=event)
    project = _project_from_payload(payload)
    if project is None:
        note("project_resolution", matched=False, reason="PROJECT_NOT_FOUND")
        return {"handled": False, "reason": "PROJECT_NOT_FOUND"}
    project_id = _project_identity(project)
    if project_id is None:
        note("project_resolution", matched=False, reason="PROJECT_NOT_REGISTERED")
        return {"handled": False, "reason": "PROJECT_NOT_REGISTERED"}
    note("project_resolution", matched=True, projectId=project_id)
    selected_host = global_hook_selection(forge_root, home=hook_home, codex_home=codex_home)
    note("host_selection", matched=selected_host == host, selectedHost=selected_host)
    if selected_host != host:
        return {"handled": False, "reason": "HOST_NOT_SELECTED"}
    directory = _invocation_directory(forge_root, project_id)
    if not directory.is_dir():
        note("pending_lookup", count=0, reason="NO_PENDING_INVOCATION")
        return {"handled": False, "reason": "NO_PENDING_INVOCATION"}
    with _INVOCATION_LOCK, _registry_file_lock(directory / ".lock"):
        _purge_expired_markers(forge_root, directory)
        pending = []
        for path in sorted(directory.glob("inv-*.json")):
            marker = _load_marker(path)
            if (isinstance(marker, dict) and marker.get("host") == host
                    and marker.get("status") == "PENDING"
                    and Path(str(marker.get("projectPath", ""))).resolve(strict=False) == project):
                pending.append((path, marker))
        note("pending_lookup", count=len(pending))
        if not pending:
            return {"handled": False, "reason": "NO_PENDING_INVOCATION"}
        identity = _host_identity(host, payload)
        note("identity_check", fields=sorted(identity), complete=_identity_is_complete(host, identity))
        if not _identity_is_complete(host, identity):
            return {"handled": False, "reason": "HOST_IDENTITY_MISSING"}
        selected = _select_pending(host, pending, identity)
        note("invocation_match", matchedCount=len(selected), candidateCount=len(pending),
             invocationIds=[marker["invocationId"] for _, marker in selected])
        if not selected:
            return {
                "handled": False,
                "reason": "AMBIGUOUS_INVOCATION",
                "count": len(pending),
            }
        if event == "after-agent-response" and host == "cursor":
            text = payload.get("text")
            if not has_meaningful_content(text):
                note("response_check", hasContent=False, reason="EMPTY_RESPONSE")
                return {"handled": False, "reason": "EMPTY_RESPONSE"}
            invocation_ids = []
            for path, marker in selected:
                marker["bufferedResponse"] = text
                marker["bufferedAt"] = _timestamp(_now())
                _write_marker(path, marker)
                invocation_ids.append(marker["invocationId"])
            note("response_buffered", count=len(invocation_ids))
            return {
                "handled": True,
                "action": "BUFFERED",
                "invocationIds": invocation_ids,
                **({"invocationId": invocation_ids[0]} if len(invocation_ids) == 1 else {}),
            }
        if event != "stop":
            note("event_check", supported=False, reason="UNSUPPORTED_EVENT")
            return {"handled": False, "reason": "UNSUPPORTED_EVENT"}
        captured = []
        empty = []
        for path, marker in selected:
            text = (
                marker.get("bufferedResponse")
                if host == "cursor"
                else payload.get("last_assistant_message")
            )
            note("response_check", invocationId=marker["invocationId"],
                 skill=marker["skill"], hasContent=has_meaningful_content(text))
            if not has_meaningful_content(text):
                _mark_missed(forge_root, marker)
                path.unlink(missing_ok=True)
                empty.append(marker["invocationId"])
                note("invocation_skipped", invocationId=marker["invocationId"], reason="EMPTY_RESPONSE")
                continue
            envelope = {
                "runtime_id": f"host-hook.{marker['invocationId']}",
                "resolved_context": {
                    "selection": {"skill": f"skill.{str(marker['skill']).replace('-', '_')}"}
                },
                "stage_progress": {"active_request": {"stage_id": "direct.host-hook"}},
            }
            result = {
                "status": "succeeded",
                "output": {"finalResponse": text},
                "metadata": {
                    "source": "native_host_hook",
                    "host": host,
                    "hostIdentity": identity,
                },
                "collection": {
                    "invocationId": marker["invocationId"],
                    "source": "HOST_HOOK",
                    "hookHost": host,
                    "hookStatus": "CAPTURED",
                },
            }
            note("collection_started", invocationId=marker["invocationId"], skill=marker["skill"])
            database = collect_imported_result(forge_root, envelope, result, project=project)
            path.unlink(missing_ok=True)
            note("collection_finished", invocationId=marker["invocationId"], stored=database is not None)
            if database is not None:
                captured.append(marker["invocationId"])
        if not captured:
            return {
                "handled": False,
                "reason": "EMPTY_RESPONSE" if empty else "COLLECTION_SKIPPED",
                "invocationIds": empty,
            }
        return {
            "handled": True,
            "action": "CAPTURED",
            "invocationIds": captured,
            **({"invocationId": captured[0]} if len(captured) == 1 else {}),
        }
