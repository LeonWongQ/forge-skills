# -*- coding: utf-8 -*-
"""Safe one-time consumption of project-scoped Forge Runtime Envelopes."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from .runtime_contracts import validate_runtime_envelope
from .runtime_discovery import RESUMABLE_STATUSES, _current_stage
from .helpers import load_json_file_safe
from .runtime_paths import forge_runtime_directory, project_runtime_directory, validate_project_runtime_directory


def _restore_claim_without_overwrite(claim: Path, path: Path) -> None:
    try:
        os.link(claim, path)
    except FileExistsError as error:
        raise RuntimeError(
            f"a new runtime already exists at {path}; retained claim: {claim}"
        ) from error
    except OSError as error:
        raise RuntimeError(
            f"runtime recovery failed; retained claim: {claim}; recovery error: {error}"
        ) from error
    try:
        os.unlink(claim)
    except OSError as error:
        raise RuntimeError(
            f"original runtime was restored at {path}; retained duplicate claim: {claim}"
        ) from error


def _validated_candidate(root: Path, runtime_directory: Path, candidate: str) -> tuple[Path, dict[str, Any]]:
    directory = runtime_directory.resolve()
    try:
        validate_project_runtime_directory(directory, expected_directory=forge_runtime_directory(root, Path.cwd()))
    except ValueError:
        # Keep consuming legacy project-local files during the migration window.
        validate_project_runtime_directory(directory, expected_directory=project_runtime_directory(Path.cwd()))
    candidate_path = Path(candidate)
    if candidate_path.name != candidate or candidate_path.suffix != ".json":
        raise ValueError("runtime path must be a direct .json filename")
    path = (directory / candidate_path.name).resolve()
    if path.parent != directory:
        raise ValueError("runtime path escapes the project runtime directory")
    document, error = load_json_file_safe(path)
    if error or not isinstance(document, dict):
        raise ValueError("runtime candidate is not a valid JSON object")
    errors = validate_runtime_envelope(root, document)
    if errors:
        raise ValueError("runtime candidate failed envelope validation")
    if document["status"] not in RESUMABLE_STATUSES:
        raise ValueError(f"runtime is not resumable: {document['status']}")
    return path, document


def consume_paused_runtime(root: Path, runtime_directory: Path, candidate: str) -> dict[str, Any]:
    """Atomically hand off one current-project Runtime and remove its persisted copy."""
    path, document = _validated_candidate(root, runtime_directory, candidate)
    claim = path.with_name(f".{path.name}.{uuid.uuid4().hex}.claim")
    try:
        os.replace(path, claim)
    except FileNotFoundError as error:
        raise ValueError("runtime was already consumed or no longer exists") from error

    try:
        stage_id, stage_index = _current_stage(document)
        payload = {
            "command": "runtime-consume-paused",
            "path": path.name,
            "runtime_id": document["runtime_id"],
            "task_statement": document["runtime_state"].get("task_statement"),
            "status": document["status"],
            "current_stage_id": stage_id,
            "current_stage_index": stage_index,
            "runtime": document,
        }
    except BaseException as error:
        try:
            _restore_claim_without_overwrite(claim, path)
        except RuntimeError as restore_error:
            raise RuntimeError(f"runtime payload construction failed; {restore_error}") from error
        raise

    try:
        claim.unlink()
    except OSError as error:
        try:
            _restore_claim_without_overwrite(claim, path)
        except RuntimeError as restore_error:
            raise RuntimeError(f"runtime cleanup failed; {restore_error}") from error
        raise RuntimeError(f"runtime cleanup failed; original runtime was restored: {path}") from error
    return payload
