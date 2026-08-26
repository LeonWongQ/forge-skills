# -*- coding: utf-8 -*-
"""Regression tests for Forge CLI registered-path validation checks."""

import json

from forge_cli.checks import check_packs, check_paths


def _error_codes(result):
    return {message["code"] for message in result["messages"] if message["level"] == "error"}


def _write_modules(root, path):
    (root / "registry" / "modules.json").write_text(
        json.dumps(
            {
                "layers": {
                    "templates": [
                        {"id": "template.test", "name": "test", "path": path}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def test_check_paths_reports_escape_not_missing(forge_root, mock_ctx, tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    _write_modules(forge_root, "../../outside.md")

    result = check_paths(forge_root, mock_ctx)

    codes = _error_codes(result)
    assert result["passed"] is False
    assert "REGISTERED_PATH_ESCAPE" in codes
    assert "PATH_MISSING" not in codes


def test_check_paths_keeps_missing_for_contained_path(forge_root, mock_ctx):
    _write_modules(forge_root, "templates/missing.md")

    result = check_paths(forge_root, mock_ctx)

    assert _error_codes(result) == {"PATH_MISSING"}


def _write_pack_fixture(root, index_path):
    pack = {
        "id": "pack.test",
        "name": "Test pack",
        "routing": {"preferred_skill": "skill.test", "keywords_any": ["test"]},
    }
    (root / "packs" / "test.json").write_text(json.dumps(pack), encoding="utf-8")
    (root / "registry" / "packs.json").write_text(
        json.dumps({"packs": [{"id": "pack.test", "name": "Test pack", "path": index_path}]}),
        encoding="utf-8",
    )
    (root / "registry" / "schemas" / "packs.schema.json").write_text("{}", encoding="utf-8")


def test_check_packs_reports_absolute_path_not_missing(forge_root, mock_ctx):
    _write_pack_fixture(forge_root, r"C:\\outside\\pack.json")

    result = check_packs(forge_root, mock_ctx)

    codes = _error_codes(result)
    assert result["passed"] is False
    assert "REGISTERED_PATH_ABSOLUTE" in codes
    assert "PACK_INDEX_PATH_MISSING" not in codes
