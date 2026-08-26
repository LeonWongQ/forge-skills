# -*- coding: utf-8 -*-
"""Materialize safe, deterministic, host-consumable Forge context bundles."""

from __future__ import annotations

import hashlib
import math
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from .helpers import portable_path_from_forge_root, resolve_registered_path
from .runtime_contracts import CONTEXT_BUNDLE_LAYER_ORDER, CONTEXT_BUNDLE_VERSION, canonical_digest, validate_context_bundle, validate_resolved_context, validate_runtime_envelope


DEFAULT_MAX_MODULE_BYTES = 256 * 1024
DEFAULT_MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MATERIALIZED_LAYERS = tuple(layer for layer in CONTEXT_BUNDLE_LAYER_ORDER if layer not in {"workflow", "packs"})


def _error(code: str, message: str, **details: Any) -> ValueError:
    suffix = f" ({details})" if details else ""
    return ValueError(f"{code}: {message}{suffix}")


def estimate_tokens(content: str) -> int:
    """Return a portable, deliberately simple token estimate for UTF-8 Markdown.

    Forge must remain provider-neutral, so it cannot claim an exact tokenizer count.
    ASCII text is estimated at four characters per token; non-ASCII characters are
    counted individually to avoid underestimating CJK-heavy instructions.
    """
    weighted_characters = sum(1 if ord(character) > 127 else 0.25 for character in content)
    return math.ceil(weighted_characters)


def _portable_path(root: Path, path: Path) -> str:
    return portable_path_from_forge_root(root, path)


def _read_module(root: Path, entry: Dict[str, Any], layer: str, position: int, max_module_bytes: int) -> Dict[str, Any]:
    module_id = entry.get("id")
    declared_path = entry.get("declared_path")
    if not isinstance(module_id, str) or not module_id:
        raise _error("CONTEXT_BUNDLE_MODULE_ID_INVALID", "module entry has no id", layer=layer)
    resolved_path, path_error = resolve_registered_path(root, declared_path)
    if path_error:
        raise _error("CONTEXT_BUNDLE_PATH_INVALID", "module path is unsafe", module_id=module_id, details=path_error)
    assert resolved_path is not None
    portable = _portable_path(root, resolved_path)
    if entry.get("resolved_path") != portable:
        raise _error("CONTEXT_BUNDLE_PATH_MISMATCH", "manifest resolved_path does not match safe registered path", module_id=module_id)
    if resolved_path.suffix.lower() != ".md":
        raise _error("CONTEXT_BUNDLE_NOT_MARKDOWN", "selected module is not a Markdown file", module_id=module_id, path=declared_path)
    if not resolved_path.is_file():
        raise _error("CONTEXT_BUNDLE_NOT_REGULAR_FILE", "selected module is not a regular file", module_id=module_id, path=declared_path)
    try:
        content_bytes = resolved_path.read_bytes()
    except OSError as error:
        raise _error("CONTEXT_BUNDLE_READ_FAILED", "cannot read selected module", module_id=module_id, error=str(error)) from error
    if len(content_bytes) > max_module_bytes:
        raise _error("CONTEXT_BUNDLE_MODULE_TOO_LARGE", "selected module exceeds byte limit", module_id=module_id, byte_size=len(content_bytes), max_module_bytes=max_module_bytes)
    if b"\x00" in content_bytes:
        raise _error("CONTEXT_BUNDLE_BINARY_CONTENT", "selected module contains NUL bytes", module_id=module_id)
    try:
        content = content_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _error("CONTEXT_BUNDLE_UTF8_INVALID", "selected module is not valid UTF-8", module_id=module_id, error=str(error)) from error
    return {
        "id": module_id,
        "layer": layer,
        "position": position,
        "sources": list(entry.get("sources", [])),
        "path": portable,
        "byte_size": len(content_bytes),
        "content_digest": f"sha256:{hashlib.sha256(content_bytes).hexdigest()}",
        "content": content,
    }


def build_context_bundle(
    root: Path,
    envelope: Dict[str, Any],
    *,
    bundle_id: Optional[str] = None,
    max_module_bytes: int = DEFAULT_MAX_MODULE_BYTES,
    max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
    max_estimated_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Capture selected Markdown modules from a valid Runtime Envelope once."""
    if max_module_bytes <= 0 or max_bundle_bytes <= 0 or (max_estimated_tokens is not None and max_estimated_tokens <= 0):
        raise _error("CONTEXT_BUNDLE_LIMIT_INVALID", "bundle byte limits must be positive")
    envelope_errors = validate_runtime_envelope(root, envelope)
    if envelope_errors:
        raise _error("CONTEXT_BUNDLE_ENVELOPE_INVALID", "runtime envelope schema validation failed", errors=envelope_errors)
    manifest = envelope["resolved_context"]
    manifest_errors = validate_resolved_context(root, manifest)
    if manifest_errors:
        raise _error("CONTEXT_BUNDLE_MANIFEST_INVALID", "resolved context schema validation failed", errors=manifest_errors)
    if not manifest.get("resolution", {}).get("ok"):
        raise _error("CONTEXT_BUNDLE_MANIFEST_UNRESOLVED", "resolved context is not safe to materialize")
    manifest_digest = canonical_digest(manifest)
    if manifest_digest != envelope.get("resolved_context_digest"):
        raise _error("CONTEXT_BUNDLE_MANIFEST_DIGEST_MISMATCH", "runtime envelope manifest digest does not match embedded manifest")

    context = manifest.get("context", {})
    layers = []
    total_bytes = 0
    total_estimated_tokens = 0
    skipped_modules = []
    seen = set()
    for layer in MATERIALIZED_LAYERS:
        entries = context.get(layer, [])
        if not entries:
            continue
        modules = []
        for position, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise _error("CONTEXT_BUNDLE_ENTRY_INVALID", "manifest layer entry must be an object", layer=layer)
            key = (layer, entry.get("id"))
            if key in seen:
                raise _error("CONTEXT_BUNDLE_DUPLICATE_MODULE", "manifest contains duplicate module entry", layer=layer, module_id=entry.get("id"))
            seen.add(key)
            module = _read_module(root, entry, layer, position, max_module_bytes)
            estimated_tokens = estimate_tokens(module["content"])
            if max_estimated_tokens is not None and total_estimated_tokens + estimated_tokens > max_estimated_tokens:
                skipped_modules.append({
                    "id": module["id"],
                    "layer": layer,
                    "estimated_tokens": estimated_tokens,
                    "reason": "estimated_token_budget_exceeded",
                })
                continue
            total_bytes += module["byte_size"]
            if total_bytes > max_bundle_bytes:
                raise _error("CONTEXT_BUNDLE_TOO_LARGE", "bundle exceeds aggregate byte limit", byte_size=total_bytes, max_bundle_bytes=max_bundle_bytes)
            total_estimated_tokens += estimated_tokens
            modules.append(module)
        if modules:
            layers.append({"id": layer, "modules": modules})

    workflow_entries = context.get("workflow", [])
    workflow = workflow_entries[0] if workflow_entries and isinstance(workflow_entries[0], dict) else {}
    bundle = {
        "schema_version": CONTEXT_BUNDLE_VERSION,
        "bundle_id": bundle_id or f"context_bundle.{uuid.uuid4().hex}",
        "runtime_id": envelope["runtime_id"],
        "source": {"resolved_context_digest": manifest_digest},
        "encoding": "utf-8",
        "workflow": {"id": workflow.get("id"), "stages": list(workflow.get("stages", []))},
        "layers": layers,
    }
    if max_estimated_tokens is not None:
        bundle["budget"] = {
            "estimation": "ascii_characters_per_token=4; non_ascii_characters_per_token=1",
            "max_estimated_tokens": max_estimated_tokens,
            "included_estimated_tokens": total_estimated_tokens,
            "skipped_modules": skipped_modules,
        }
    bundle["bundle_digest"] = canonical_digest(bundle)
    bundle_errors = validate_context_bundle(root, bundle)
    if bundle_errors:
        raise _error("CONTEXT_BUNDLE_SCHEMA_INVALID", "generated bundle failed schema validation", errors=bundle_errors)
    return bundle
