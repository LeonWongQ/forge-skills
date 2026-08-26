import json

import pytest

from forge_cli.renderers import write_report_file_exclusive


def test_exclusive_report_write_preserves_existing_document(tmp_path):
    path = tmp_path / "runtime.json"
    write_report_file_exclusive(path, {"writer": "first"})

    with pytest.raises(FileExistsError):
        write_report_file_exclusive(path, {"writer": "second"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"writer": "first"}
