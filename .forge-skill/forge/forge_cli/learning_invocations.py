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
CURSOR_TRANSCRIPT_TAIL_BYTES = 2_000_000
MAX_SHARED_CAPTURE_DATABASES = 11
_INVOCATION_LOCK = threading.Lock()
_HOST_ENVIRONMENT_MARKERS = {
    "codex": ("CODEX_SESSION_ID", "CODEX_THREAD_ID"),
    "claude-code": ("CLAUDE_CODE_SESSION_ID", "CLAUDECODE"),
    "cursor": ("CURSOR_CONVERSATION_ID", "CURSOR_GENERATION_ID"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def current_host_from_environment() -> str | None:
    detected = [
        host for host, markers in _HOST_ENVIRONMENT_MARKERS.items()
        if any(os.getenv(marker) for marker in markers)
    ]
    return detected[0] if len(detected) == 1 else None


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
        session_id = os.getenv("CLAUDE_CODE_SESSION_ID") or os.getenv("CLAUDE_SESSION_ID")
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
    current_host: str,
    hook_home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    """Create one correlation marker only when native Hook capture is selected."""
    if current_host not in {*_HOST_ENVIRONMENT_MARKERS, "unknown"}:
        raise ValueError(f"unsupported current host: {current_host}")
    project = project.resolve()
    normalized = skill.removeprefix("skill.").replace("_", "-")
    enabled = _load_enabled_skills(forge_root, project)
    if enabled is None or normalized not in enabled or normalized == "learning-collector":
        return {"started": False, "reason": "SKILL_NOT_ENABLED"}
    project_id = _project_id(forge_root, project)
    host = global_hook_selection(forge_root, home=hook_home, codex_home=codex_home)
    invocation_id = f"inv-{uuid.uuid4()}"
    hook_matches_current = isinstance(host, str) and current_host == host
    result = {
        "started": True,
        "invocationId": invocation_id,
        "projectId": project_id,
        "skill": normalized,
        "hookHost": host if hook_matches_current else None,
        "hookExpected": hook_matches_current,
    }
    if not isinstance(host, str):
        return result
    if not hook_matches_current:
        result["reason"] = (
            "CURRENT_HOST_UNKNOWN" if current_host == "unknown"
            else "HOOK_HOST_MISMATCH"
        )
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
    markers = [(path, _load_marker(path)) for path in directory.glob("inv-*.json")]
    removed: set[Path] = set()
    for path, marker in markers:
        if path in removed:
            continue
        expires = _parse_timestamp(marker.get("expiresAt")) if marker else None
        if marker is None or expires is None or expires <= now:
            shared_capture_id = marker.get("sharedCaptureId") if marker else None
            if isinstance(shared_capture_id, str) and shared_capture_id.strip():
                group = [
                    (candidate_path, candidate)
                    for candidate_path, candidate in markers
                    if isinstance(candidate, dict)
                    and candidate.get("sharedCaptureId") == shared_capture_id
                ]
                _clean_failed_shared_capture(forge_root, group)
                _remove_invocation_markers(group)
                removed.update(candidate_path for candidate_path, _candidate in group)
                continue
            if marker is not None:
                _mark_missed(forge_root, marker)
            path.unlink(missing_ok=True)
            removed.add(path)


def _project_root(candidate: Path) -> Path | None:
    candidate = candidate.resolve(strict=False)
    if candidate.is_file():
        candidate = candidate.parent
    for path in (candidate, *candidate.parents):
        if (path / ".forge-skill" / "learning" / "project.json").is_file():
            return path
    return None


def _payload_path(value: str) -> Path:
    """Normalize Cursor's slash-prefixed Windows drive paths."""
    normalized = value.strip()
    if (
        os.name == "nt"
        and len(normalized) >= 4
        and normalized[0] in "/\\"
        and normalized[1].isalpha()
        and normalized[2] == ":"
        and normalized[3] in "/\\"
    ):
        normalized = normalized[1:]
    return Path(normalized)


def _cursor_projects_root() -> Path:
    return (Path.home() / ".cursor" / "projects").resolve(strict=False)


def _cursor_transcript_response(payload: dict[str, Any]) -> str | None:
    """Recover the final Cursor response from its bounded local transcript tail."""
    value = payload.get("transcript_path")
    if not isinstance(value, str) or not value.strip():
        return None
    path = _payload_path(value).resolve(strict=False)
    root = _cursor_projects_root()
    if path.suffix.casefold() != ".jsonl" or not path.is_relative_to(root):
        return None
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            offset = max(0, size - CURSOR_TRANSCRIPT_TAIL_BYTES)
            handle.seek(offset)
            raw = handle.read(CURSOR_TRANSCRIPT_TAIL_BYTES)
    except OSError:
        return None
    if offset:
        _, separator, raw = raw.partition(b"\n")
        if not separator:
            return None
    try:
        lines = raw.decode("utf-8-sig", errors="strict").splitlines()
    except UnicodeDecodeError:
        return None
    completed_turn = False
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if not completed_turn:
            if entry.get("role") in {"user", "assistant"}:
                return None
            if entry.get("type") != "turn_ended":
                continue
            if entry.get("status") != "success":
                return None
            completed_turn = True
            continue
        if entry.get("role") == "user":
            return None
        if entry.get("role") != "assistant":
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return content if has_meaningful_content(content) else None
        if not isinstance(content, list):
            continue
        parts = [
            part.get("text")
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
            and has_meaningful_content(part.get("text"))
        ]
        if parts:
            return "\n".join(parts)
    return None


def _normalize_host_response(value: Any) -> str | None:
    """Normalize transport line endings while preserving user-visible content."""
    if not isinstance(value, str):
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if has_meaningful_content(normalized) else None


def _response_profile(text: str) -> dict[str, Any]:
    """Describe response shape without applying Skill-specific assumptions."""
    stripped = text.lstrip()
    response_format = "TEXT"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        if "```" in text or any(line.lstrip().startswith("#") for line in text.splitlines()):
            response_format = "MARKDOWN"
    else:
        if isinstance(parsed, (dict, list)):
            response_format = "JSON"
    return {
        "format": response_format,
        "characters": len(text),
        "nonWhitespaceCharacters": sum(not character.isspace() for character in text),
        "lines": text.count("\n") + 1,
        "startsWithHeading": stripped.startswith("#"),
        "codeFenceCount": text.count("```") // 2,
    }


def _capture_attribution(
    host: str,
    identity: dict[str, str],
    selected: list[tuple[Path, dict[str, Any]]],
) -> str:
    if len(selected) > 1:
        return "SHARED_HOST_TURN"
    if _identity_is_turn_unique(host, identity):
        return "TURN_UNIQUE"
    if identity:
        return "SESSION_SCOPED"
    return "SOLE_PENDING"


def _hook_capture_persisted(database: Path | None, invocation_id: str, host: str) -> bool:
    """Verify the write instead of treating a database path as a successful update."""
    if database is None:
        return False
    connection = connect_database(database)
    try:
        row = connection.execute(
            "SELECT hook_status, hook_host FROM learning_records WHERE invocation_id = ?",
            (invocation_id,),
        ).fetchone()
    finally:
        connection.close()
    return (
        row is not None
        and row["hook_status"] == "CAPTURED"
        and row["hook_host"] == host
    )


def _complete_shared_capture(
    captured: list[tuple[Path, str]], shared_capture_id: str,
) -> None:
    """Publish a shared group only after every member write has finished."""
    database_paths = list(dict.fromkeys(database.resolve() for database, _invocation_id in captured))
    if not database_paths or len(database_paths) > MAX_SHARED_CAPTURE_DATABASES:
        raise RuntimeError("shared Hook capture has an invalid database count")
    aliases = {database_paths[0]: "main"}
    connection = connect_database(database_paths[0])
    try:
        for index, database in enumerate(database_paths[1:], start=1):
            alias = f"skill_{index}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(database),))
            aliases[database] = alias
        for alias in aliases.values():
            mode = connection.execute(f"PRAGMA {alias}.journal_mode=TRUNCATE").fetchone()[0]
            if str(mode).casefold() != "truncate":
                raise sqlite3.OperationalError(
                    f"shared Hook capture requires rollback journaling for {alias}"
                )
        connection.execute("BEGIN IMMEDIATE")
        try:
            for database, invocation_id in captured:
                alias = aliases[database.resolve()]
                cursor = connection.execute(
                    f"UPDATE {alias}.learning_records SET shared_capture_complete = 1 "
                    "WHERE invocation_id = ? AND shared_capture_id = ? "
                    "AND hook_status = 'CAPTURED'",
                    (invocation_id, shared_capture_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("shared Hook capture member could not be completed")
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()


def _clean_failed_shared_capture(
    forge_root: Path,
    selected: list[tuple[Path, dict[str, Any]]],
) -> None:
    """Atomically remove partial Hook evidence for a failed shared group."""
    members = []
    for _path, marker in selected:
        database = _project_database(
            forge_root, str(marker["projectId"]), str(marker["skill"]),
        )
        if database.is_file():
            members.append((database.resolve(), str(marker["invocationId"])))
    if not members:
        return
    database_paths = list(dict.fromkeys(database for database, _invocation_id in members))
    if len(database_paths) > MAX_SHARED_CAPTURE_DATABASES:
        raise RuntimeError("failed shared Hook cleanup has an invalid database count")
    aliases = {database_paths[0]: "main"}
    connection = connect_database(database_paths[0])
    try:
        for index, database in enumerate(database_paths[1:], start=1):
            alias = f"skill_{index}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(database),))
            aliases[database] = alias
        for alias in aliases.values():
            mode = connection.execute(f"PRAGMA {alias}.journal_mode=TRUNCATE").fetchone()[0]
            if str(mode).casefold() != "truncate":
                raise sqlite3.OperationalError(
                    f"failed shared Hook cleanup requires rollback journaling for {alias}"
                )
        connection.execute("BEGIN IMMEDIATE")
        try:
            for database, invocation_id in members:
                alias = aliases[database]
                connection.execute(
                    f"DELETE FROM {alias}.learning_records "
                    "WHERE invocation_id = ? AND reviewed = 0 "
                    "AND capture_source = 'HOST_HOOK'",
                    (invocation_id,),
                )
                connection.execute(
                    f"UPDATE {alias}.learning_records "
                    "SET hook_status = 'MISSED', shared_capture_id = NULL, "
                    "shared_capture_complete = 0, host_output_json = NULL, "
                    "hook_captured_at = NULL, metadata_json = CASE "
                    "WHEN json_valid(metadata_json) THEN json_remove(metadata_json, '$.hookCapture') "
                    "ELSE metadata_json END "
                    "WHERE invocation_id = ? AND reviewed = 0 "
                    "AND capture_source = 'SKILL_CONTRACT'",
                    (invocation_id,),
                )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()


def _remove_invocation_markers(
    selected: list[tuple[Path, dict[str, Any]]],
) -> None:
    for path, _marker in selected:
        path.unlink(missing_ok=True)


def _project_from_payload(payload: dict[str, Any]) -> Path | None:
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        project = _project_root(_payload_path(cwd))
        if project is not None:
            return project
    roots = payload.get("workspace_roots")
    if isinstance(roots, list):
        candidates = {
            project
            for item in roots
            if isinstance(item, str) and item.strip()
            for project in [_project_root(_payload_path(item))]
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
        selected_skills = {str(marker["skill"]) for _path, marker in selected}
        if len(selected_skills) != len(selected):
            invocation_ids = []
            for _path, marker in selected:
                _mark_missed(forge_root, marker)
                invocation_ids.append(marker["invocationId"])
            _remove_invocation_markers(selected)
            note(
                "invocation_skipped", reason="DUPLICATE_SKILL_INVOCATIONS",
                matchedInvocationCount=len(selected),
                matchedSkillCount=len(selected_skills),
            )
            return {
                "handled": False,
                "reason": "DUPLICATE_SKILL_INVOCATIONS",
                "invocationIds": invocation_ids,
            }
        if len(selected_skills) > MAX_SHARED_CAPTURE_DATABASES:
            invocation_ids = []
            for path, marker in selected:
                _mark_missed(forge_root, marker)
                path.unlink(missing_ok=True)
                invocation_ids.append(marker["invocationId"])
            note(
                "invocation_skipped", reason="SHARED_GROUP_TOO_LARGE",
                matchedSkillCount=len(selected_skills),
                maximum=MAX_SHARED_CAPTURE_DATABASES,
            )
            return {
                "handled": False,
                "reason": "SHARED_GROUP_TOO_LARGE",
                "count": len(selected_skills),
                "maximum": MAX_SHARED_CAPTURE_DATABASES,
                "invocationIds": invocation_ids,
            }
        shared_capture_id = None
        if len(selected) > 1:
            existing_shared_ids = {
                marker.get("sharedCaptureId")
                for _path, marker in selected
                if isinstance(marker.get("sharedCaptureId"), str)
                and marker["sharedCaptureId"].strip()
            }
            shared_capture_id = (
                next(iter(existing_shared_ids))
                if len(existing_shared_ids) == 1
                else f"shared-{uuid.uuid4()}"
            )
            for path, marker in selected:
                if marker.get("sharedCaptureId") != shared_capture_id:
                    marker["sharedCaptureId"] = shared_capture_id
                    _write_marker(path, marker)
        if event == "after-agent-response" and host == "cursor":
            text = _normalize_host_response(payload.get("text"))
            if text is None:
                note("response_check", hasContent=False, reason="EMPTY_RESPONSE")
                return {"handled": False, "reason": "EMPTY_RESPONSE"}
            invocation_ids = []
            for path, marker in selected:
                marker["bufferedResponse"] = text
                marker["bufferedAt"] = _timestamp(_now())
                marker["bufferedSource"] = "cursor-after-agent-response"
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
        skipped = []
        completed_members: list[tuple[Path, str]] = []
        finalized_paths: list[Path] = []
        attribution = _capture_attribution(host, identity, selected)
        matched_skills = sorted({str(marker["skill"]) for _, marker in selected})
        for path, marker in selected:
            response_source = "stop-payload"
            raw_response = (
                marker.get("bufferedResponse")
                if host == "cursor"
                else payload.get("last_assistant_message")
            )
            if host == "cursor" and not has_meaningful_content(raw_response):
                raw_response = _cursor_transcript_response(payload)
                response_source = "cursor-transcript"
                note(
                    "response_recovered", invocationId=marker["invocationId"],
                    source="cursor_transcript",
                    hasContent=has_meaningful_content(raw_response),
                )
            elif host == "cursor":
                response_source = str(marker.get("bufferedSource") or "cursor-buffer")
            text = _normalize_host_response(raw_response)
            note("response_check", invocationId=marker["invocationId"],
                 skill=marker["skill"], hasContent=text is not None)
            if text is None:
                if shared_capture_id is None:
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
                    "hookCapture": {
                        "schemaVersion": "1.0",
                        "skill": marker["skill"],
                        "host": host,
                        "event": event,
                        "responseSource": response_source,
                        "attribution": attribution,
                        "matchedInvocationCount": len(selected),
                        "matchedSkills": matched_skills,
                        "response": _response_profile(text),
                        **(
                            {"sharedCaptureId": shared_capture_id}
                            if shared_capture_id is not None else {}
                        ),
                    },
                },
                "collection": {
                    "invocationId": marker["invocationId"],
                    "source": "HOST_HOOK",
                    "hookHost": host,
                    "hookStatus": "CAPTURED",
                },
            }
            note("collection_started", invocationId=marker["invocationId"], skill=marker["skill"])
            try:
                database = collect_imported_result(forge_root, envelope, result, project=project)
                stored = _hook_capture_persisted(database, marker["invocationId"], host)
            except Exception:
                if shared_capture_id is not None:
                    _clean_failed_shared_capture(forge_root, selected)
                    _remove_invocation_markers(selected)
                    note("shared_capture_failed", reason="COLLECTION_ERROR")
                raise
            note("collection_finished", invocationId=marker["invocationId"], stored=stored)
            if stored:
                captured.append(marker["invocationId"])
                if database is not None:
                    completed_members.append((database, marker["invocationId"]))
            else:
                skipped.append(marker["invocationId"])
            finalized_paths.append(path)
        if shared_capture_id is not None and len(completed_members) != len(selected):
            _clean_failed_shared_capture(forge_root, selected)
            _remove_invocation_markers(selected)
            note(
                "shared_capture_incomplete", completedCount=len(completed_members),
                expectedCount=len(selected),
            )
            return {
                "handled": False,
                "reason": "SHARED_CAPTURE_INCOMPLETE",
                "invocationIds": [marker["invocationId"] for _path, marker in selected],
            }
        if shared_capture_id is not None:
            try:
                _complete_shared_capture(completed_members, shared_capture_id)
            except Exception:
                _clean_failed_shared_capture(forge_root, selected)
                _remove_invocation_markers(selected)
                note("shared_capture_failed", reason="COMPLETION_ERROR")
                raise
            note("shared_capture_completed", count=len(completed_members))
        for path in finalized_paths:
            path.unlink(missing_ok=True)
        if not captured:
            return {
                "handled": False,
                "reason": "EMPTY_RESPONSE" if empty else "COLLECTION_SKIPPED",
                "invocationIds": empty or skipped,
            }
        return {
            "handled": True,
            "action": "CAPTURED",
            "invocationIds": captured,
            **({"invocationId": captured[0]} if len(captured) == 1 else {}),
        }
