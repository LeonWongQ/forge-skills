"""Lifecycle management for the loopback-only learning review service."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _skill_root(forge_root: Path) -> Path:
    base = forge_root.parent if forge_root.name == "forge" else forge_root
    return base / "skills" / "learning-collector"


def _state_path(forge_root: Path) -> Path:
    return _skill_root(forge_root) / "review-service.json"


def _load_state(forge_root: Path) -> dict | None:
    try:
        value = json.loads(_state_path(forge_root).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _save_state(forge_root: Path, state: dict) -> None:
    path = _state_path(forge_root)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _remove_state(forge_root: Path) -> None:
    try:
        _state_path(forge_root).unlink()
    except FileNotFoundError:
        pass


def _probe(state: dict) -> bool:
    try:
        with urlopen(f"{state['url']}/api/service", timeout=0.5) as response:
            value = json.loads(response.read())
        return value.get("token") == state.get("token") and value.get("pid") == state.get("pid")
    except (OSError, URLError, ValueError, json.JSONDecodeError, KeyError):
        return False


def _available_port(start: int = 8765) -> int:
    for port in range(start, start + 50):
        with socket.socket() as candidate:
            try:
                candidate.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("no available learning review port in range 8765-8814")


def start_review_service(forge_root: Path) -> dict:
    existing = _load_state(forge_root)
    if existing and _probe(existing):
        return {**existing, "status": "already_running"}
    if existing:
        _remove_state(forge_root)
    script = _skill_root(forge_root) / "scripts" / "review_server.py"
    if not script.is_file():
        raise RuntimeError(f"learning review server is missing: {script}")
    port = _available_port()
    token = uuid.uuid4().hex
    command = [sys.executable, str(script), "--port", str(port), "--token", token]
    kwargs = {
        "cwd": str(_skill_root(forge_root)), "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    state = {
        "schemaVersion": "1.0", "pid": process.pid, "port": port,
        "url": f"http://127.0.0.1:{port}", "token": token, "startedAt": _now(),
    }
    for _ in range(40):
        if _probe(state):
            _save_state(forge_root, state)
            return {**state, "status": "started"}
        if process.poll() is not None:
            break
        time.sleep(0.1)
    try:
        process.terminate()
    except OSError:
        pass
    raise RuntimeError("learning review service did not start")


def stop_review_service(forge_root: Path) -> dict:
    state = _load_state(forge_root)
    if not state:
        return {"status": "not_running"}
    if not _probe(state):
        _remove_state(forge_root)
        return {"status": "stale_state_removed"}
    os.kill(int(state["pid"]), signal.SIGTERM)
    for _ in range(30):
        if not _probe(state):
            break
        time.sleep(0.1)
    _remove_state(forge_root)
    return {"status": "stopped", "pid": state["pid"], "url": state["url"]}
