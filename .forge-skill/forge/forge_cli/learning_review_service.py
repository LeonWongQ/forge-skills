"""Lifecycle management for the loopback-only learning review service."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .data_paths import forge_data_root
from .learning_collector import _registry_file_lock
from .renderers import write_report_file


_SERVICE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _skill_root(forge_root: Path) -> Path:
    base = forge_root.parent if forge_root.name == "forge" else forge_root
    return base / "skills" / "learning-collector"


def _state_path(forge_root: Path) -> Path:
    return forge_data_root(forge_root) / "services" / "learning-review-service.json"


def _legacy_state_path(forge_root: Path) -> Path:
    return _skill_root(forge_root) / "review-service.json"


def _load_state(forge_root: Path) -> dict | None:
    try:
        value = json.loads(_state_path(forge_root).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        try:
            value = json.loads(_legacy_state_path(forge_root).read_text(encoding="utf-8"))
            if isinstance(value, dict):
                _save_state(forge_root, value)
                return value
        except (OSError, json.JSONDecodeError):
            pass
        return None


def _save_state(forge_root: Path, state: dict) -> None:
    write_report_file(_state_path(forge_root), state)


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


def _process_alive(state: dict) -> bool | None:
    pid = state.get("pid")
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform == "win32":
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _windows_process_alive(pid: int) -> bool | None:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    open_process.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (ctypes.c_void_p,)
    close_handle.restype = ctypes.c_int
    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        close_handle(handle)
        return True
    error = ctypes.get_last_error()
    if error == 5:  # ERROR_ACCESS_DENIED still proves that the process exists.
        return True
    if error == 87:  # ERROR_INVALID_PARAMETER means the PID does not exist.
        return False
    return None


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
    with _SERVICE_LOCK, _registry_file_lock(_state_path(forge_root)):
        return _start_review_service_locked(forge_root)


def _start_review_service_locked(forge_root: Path) -> dict:
    existing = _load_state(forge_root)
    if existing and _probe(existing):
        return {**existing, "status": "already_running"}
    if existing:
        if _process_alive(existing) is not False:
            raise RuntimeError("learning review service is unresponsive; retained service state to avoid a duplicate process")
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
    try:
        for _ in range(40):
            if _probe(state):
                _save_state(forge_root, state)
                return {**state, "status": "started"}
            if process.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError("learning review service did not start")
    except BaseException as error:
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired) as cleanup_error:
            raise RuntimeError(f"learning review startup failed; process cleanup failed: {type(cleanup_error).__name__}") from error
        raise


def stop_review_service(forge_root: Path) -> dict:
    with _SERVICE_LOCK, _registry_file_lock(_state_path(forge_root)):
        return _stop_review_service_locked(forge_root)


def _stop_review_service_locked(forge_root: Path) -> dict:
    state = _load_state(forge_root)
    if not state:
        return {"status": "not_running"}
    if not _probe(state):
        if _process_alive(state) is not False:
            raise RuntimeError("learning review service is unresponsive; retained service state because its process may still be running")
        _remove_state(forge_root)
        return {"status": "stale_state_removed"}
    try:
        os.kill(int(state["pid"]), signal.SIGTERM)
    except OSError as error:
        if _process_alive(state) is not False:
            raise RuntimeError("could not stop learning review service; retained service state") from error
    for _ in range(30):
        if _process_alive(state) is False:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("learning review service has not exited; retained service state")
    _remove_state(forge_root)
    return {"status": "stopped", "pid": state["pid"], "url": state["url"]}
