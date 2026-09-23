import json

import pytest

from forge_cli.renderers import write_report_file, write_report_file_exclusive
from forge_cli import renderers


def test_exclusive_report_write_preserves_existing_document(tmp_path):
    path = tmp_path / "runtime.json"
    write_report_file_exclusive(path, {"writer": "first"})

    with pytest.raises(FileExistsError):
        write_report_file_exclusive(path, {"writer": "second"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"writer": "first"}


def test_atomic_report_write_preserves_old_file_on_serialization_failure(tmp_path):
    path = tmp_path / "runtime.json"
    write_report_file(path, {"writer": "first"})
    with pytest.raises(TypeError):
        write_report_file(path, {"invalid": object()})
    assert json.loads(path.read_text(encoding="utf-8")) == {"writer": "first"}
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_report_write_preserves_old_file_on_replace_failure(tmp_path, monkeypatch):
    path = tmp_path / "runtime.json"
    write_report_file(path, {"writer": "first"})

    def fail_replace(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(renderers.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        write_report_file(path, {"writer": "second"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"writer": "first"}
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_report_write_replaces_complete_document(tmp_path):
    path = tmp_path / "nested" / "runtime.json"
    write_report_file(path, {"writer": "first"})
    write_report_file(path, {"writer": "second", "text": "Unicode \U0001f600"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"writer": "second", "text": "Unicode \U0001f600"}
    assert list(path.parent.iterdir()) == [path]
