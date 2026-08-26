# -*- coding: utf-8 -*-
"""Tests for scripts/_shared.py — shared utilities for validation scripts."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
_scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_scripts_dir))

from _shared import (
    FORGE_ROOT,
    WORKSPACE_ROOT,
    OK,
    FAIL,
    WARN,
    collect_ids,
    file_exists,
    forge_path,
    load_json,
    workspace_path,
)


class TestConstants:
    def test_status_values_are_distinct(self):
        assert OK != FAIL
        assert OK != WARN
        assert FAIL != WARN

    def test_forge_root_exists(self):
        assert FORGE_ROOT.exists()
        assert FORGE_ROOT.name == "forge"

    def test_workspace_root_is_parent_of_forge(self):
        assert WORKSPACE_ROOT == FORGE_ROOT.parent


class TestForgePath:
    def test_resolves_relative_to_forge_root(self):
        result = forge_path("registry")
        assert result == FORGE_ROOT / "registry"

    def test_resolves_nested_path(self):
        result = forge_path("registry/schemas")
        assert result == FORGE_ROOT / "registry" / "schemas"


class TestWorkspacePath:
    def test_resolves_relative_to_workspace(self):
        result = workspace_path("skills")
        assert result == WORKSPACE_ROOT / "skills"


class TestLoadJson:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        data = load_json(f)
        assert data == {"key": "value"}

    def test_missing_file_returns_none(self):
        result = load_json(Path("/nonexistent/file.json"))
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        result = load_json(f)
        assert result is None


class TestCollectIds:
    def test_flat_list(self):
        registry = {
            "items": [
                {"id": "item.one", "name": "One"},
                {"id": "item.two", "name": "Two"},
            ]
        }
        result = collect_ids(registry, "items")
        assert result == {"item.one": {"id": "item.one", "name": "One"},
                          "item.two": {"id": "item.two", "name": "Two"}}

    def test_layered_dict(self):
        registry = {
            "layers": {
                "layer1": [
                    {"id": "a.one", "name": "A1"},
                ],
                "layer2": [
                    {"id": "b.one", "name": "B1"},
                    {"id": "b.two", "name": "B2"},
                ],
            }
        }
        result = collect_ids(registry, "layers")
        assert len(result) == 3
        assert "a.one" in result
        assert "b.two" in result

    def test_missing_ids_skipped(self):
        registry = {
            "items": [
                {"name": "No ID"},
                {"id": "item.ok", "name": "OK"},
            ]
        }
        result = collect_ids(registry, "items")
        assert len(result) == 1
        assert "item.ok" in result

    def test_non_list_value(self):
        registry = {"items": "not a list"}
        result = collect_ids(registry, "items")
        assert result == {}


class TestFileExists:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("hello")
        assert file_exists(f) is True

    def test_nonexistent_file(self, tmp_path):
        assert file_exists(tmp_path / "nope.txt") is False

    def test_directory_is_not_file(self, tmp_path):
        assert file_exists(tmp_path) is False
