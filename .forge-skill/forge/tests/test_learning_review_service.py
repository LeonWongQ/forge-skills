"""Isolated process lifecycle tests; no real service or network calls."""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from forge_cli import learning_review_service as service


def test_process_alive_checks_without_signaling_current_process():
    assert service._process_alive({"pid": os.getpid()}) is True
    assert service._process_alive({"pid": 2_147_483_647}) is False
    assert service._process_alive({"pid": "invalid"}) is None


@pytest.fixture
def launch(tmp_path, monkeypatch):
    root = tmp_path / "forge"
    script = tmp_path / "skills" / "learning-collector" / "scripts" / "review_server.py"
    script.parent.mkdir(parents=True)
    script.touch()
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "forge-data"))
    process = Mock(pid=123, **{"poll.return_value": None})
    popen = Mock(return_value=process)
    monkeypatch.setattr(service.subprocess, "Popen", popen)
    monkeypatch.setattr(service, "_available_port", lambda: 8765)
    monkeypatch.setattr(service, "_probe", lambda _state: True)
    return root, process, popen


def test_start_persists_state_and_second_start_reuses_process(launch):
    root, process, popen = launch
    state = service.start_review_service(root)
    assert state["status"] == "started"
    assert json.loads(service._state_path(root).read_text(encoding="utf-8"))["pid"] == 123
    assert service.start_review_service(root)["status"] == "already_running"
    popen.assert_called_once()
    process.terminate.assert_not_called()


def test_concurrent_starts_spawn_only_one_process(launch):
    root, _process, popen = launch
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(service.start_review_service, [root, root]))
    assert sorted(result["status"] for result in results) == ["already_running", "started"]
    popen.assert_called_once()


def test_start_does_not_replace_unresponsive_live_service(launch, monkeypatch):
    root, _process, popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_probe", lambda _state: False)
    monkeypatch.setattr(service, "_process_alive", lambda _state: True)

    with pytest.raises(RuntimeError, match="unresponsive"):
        service.start_review_service(root)

    assert service._state_path(root).exists()
    popen.assert_called_once()


def test_start_replaces_state_only_after_process_exits(launch, monkeypatch):
    root, _process, popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_probe", Mock(side_effect=[False, True]))
    monkeypatch.setattr(service, "_process_alive", lambda _state: False)

    assert service.start_review_service(root)["status"] == "started"
    assert popen.call_count == 2
    assert service._state_path(root).exists()


def test_stop_preserves_state_when_health_probe_fails_but_process_lives(launch, monkeypatch):
    root, _process, _popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_probe", lambda _state: False)
    monkeypatch.setattr(service, "_process_alive", lambda _state: True)
    terminate = Mock()
    monkeypatch.setattr(service.os, "kill", terminate)

    with pytest.raises(RuntimeError, match="unresponsive"):
        service.stop_review_service(root)

    assert service._state_path(root).exists()
    terminate.assert_not_called()


def test_stop_removes_state_after_confirmed_exit(launch, monkeypatch):
    root, _process, _popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_process_alive", lambda _state: False)
    terminate = Mock()
    monkeypatch.setattr(service.os, "kill", terminate)

    assert service.stop_review_service(root)["status"] == "stopped"
    terminate.assert_called_once_with(123, service.signal.SIGTERM)
    assert not service._state_path(root).exists()


def test_stop_retains_state_if_process_ignores_termination(launch, monkeypatch):
    root, _process, _popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_process_alive", lambda _state: True)
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)
    terminate = Mock()
    monkeypatch.setattr(service.os, "kill", terminate)

    with pytest.raises(RuntimeError, match="has not exited"):
        service.stop_review_service(root)

    terminate.assert_called_once_with(123, service.signal.SIGTERM)
    assert service._state_path(root).exists()


def test_stop_removes_stale_state_when_process_is_gone(launch, monkeypatch):
    root, _process, _popen = launch
    service.start_review_service(root)
    monkeypatch.setattr(service, "_probe", lambda _state: False)
    monkeypatch.setattr(service, "_process_alive", lambda _state: False)

    assert service.stop_review_service(root)["status"] == "stale_state_removed"
    assert not service._state_path(root).exists()


@pytest.mark.parametrize("timeout", [False, True])
def test_failed_state_save_reaps_spawned_process(launch, monkeypatch, timeout):
    root, process, _popen = launch
    failure = OSError("state write denied")
    monkeypatch.setattr(service, "_save_state", Mock(side_effect=failure))
    if timeout:
        process.wait.side_effect = [subprocess.TimeoutExpired("server", 2), 0]
    with pytest.raises(OSError) as caught:
        service.start_review_service(root)
    assert caught.value is failure
    process.terminate.assert_called_once()
    if timeout:
        process.kill.assert_called_once()
        assert process.wait.call_count == 2
    else:
        process.kill.assert_not_called()
        process.wait.assert_called_once_with(timeout=2)
    assert not service._state_path(root).exists()
