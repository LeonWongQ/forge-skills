#!/usr/bin/env python3
"""Record one direct host Skill result from a JSON document on stdin."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

MAX_INPUT_BYTES = 2_000_000
TRANSPORT_FIELDS = {"status", "diagnostics", "metadata"}


def read_payload() -> dict:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if not raw.strip() or len(raw) > MAX_INPUT_BYTES:
        raise SystemExit("direct result JSON is empty or exceeds 2 MB")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise SystemExit(
            f"direct result must be UTF-8 bytes; decoding failed at byte {error.start}"
        ) from None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"direct result is not valid JSON: {error.msg}") from None
    if not isinstance(payload, dict):
        raise SystemExit("direct result must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--forge-root", type=Path, default=None)
    args = parser.parse_args()
    payload = read_payload()

    skill_root = Path(__file__).resolve().parents[1]
    forge_root = (args.forge_root or (skill_root.parent.parent / "forge")).resolve()
    sys.path.insert(0, str(forge_root))
    from forge_cli.learning_collector import collect_imported_result, validate_no_lone_surrogates

    try:
        validate_no_lone_surrogates(payload)
    except ValueError as error:
        raise SystemExit(f"direct result has invalid Unicode: {error}") from None

    normalized = args.skill.removeprefix("skill.").replace("_", "-")
    output = {key: value for key, value in payload.items() if key not in TRANSPORT_FIELDS}
    envelope = {
        "runtime_id": f"codex-direct.{uuid.uuid4().hex}",
        "resolved_context": {"selection": {"skill": f"skill.{normalized.replace('-', '_')}"}},
        "stage_progress": {"active_request": {"stage_id": "direct.delivery"}},
    }
    result = {
        "status": payload.get("status", "succeeded"),
        "output": output,
        "diagnostics": payload.get("diagnostics"),
        "metadata": {
            **(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
            "source": "direct_host_skill",
            "skill": normalized,
        },
    }
    database = collect_imported_result(forge_root, envelope, result, project=args.project)
    print(json.dumps({"collected": database is not None, "database": str(database) if database else None}, ensure_ascii=True))


if __name__ == "__main__":
    main()
