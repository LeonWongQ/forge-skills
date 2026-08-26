# -*- coding: utf-8 -*-
"""Tests for forge_cli.helpers — path resolution, JSON I/O, text normalization."""

import json
import os
from pathlib import Path

import pytest

import forge_cli.helpers as helpers

from forge_cli.helpers import (
    claude_root_from_forge_root,
    is_string_2d_list,
    is_string_list,
    load_json,
    load_json_file_safe,
    normalize_text,
    portable_path_from_forge_root,
    resolve_registered_path,
    resolve_root,
    resolved_workspace_root_from_forge_root,
    safe_name_to_id_suffix,
)


class TestResolveRoot:
    def test_explicit_path(self, tmp_path):
        result = resolve_root(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FORGE_ROOT", str(tmp_path))
        result = resolve_root(None)
        assert result == tmp_path.resolve()

    def test_explicit_codex_root_preserves_its_logical_prefix(self, tmp_path):
        root = tmp_path / ".codex" / "forge"
        root.mkdir(parents=True)

        assert resolve_root(str(root)) == root.absolute()

    def test_discovers_codex_installation_from_project_directory(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        root = project / ".codex" / "forge"
        (root / "registry").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# Forge", encoding="utf-8")
        monkeypatch.chdir(project)

        assert resolve_root(None) == root.absolute()

    def test_discovers_repository_source_from_project_directory(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        root = project / ".forge-skill" / "forge"
        (root / "registry").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# Forge", encoding="utf-8")
        monkeypatch.chdir(project)

        assert resolve_root(None) == root.absolute()

    def test_project_installation_wins_over_global_codex_fallback(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project" / ".codex" / "forge"
        global_root = tmp_path / "home" / ".codex" / "forge"
        for root in (project_root, global_root):
            (root / "registry").mkdir(parents=True)
            (root / "CLAUDE.md").write_text("# Forge", encoding="utf-8")
        monkeypatch.chdir(tmp_path / "project")
        monkeypatch.setattr(helpers.Path, "home", classmethod(lambda cls: tmp_path / "home"))

        assert resolve_root(None) == project_root.absolute()

    def test_discovers_global_codex_fallback_when_project_has_no_forge(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        global_root = tmp_path / "home" / ".codex" / "forge"
        project.mkdir()
        (global_root / "registry").mkdir(parents=True)
        (global_root / "CLAUDE.md").write_text("# Forge", encoding="utf-8")
        monkeypatch.chdir(project)
        monkeypatch.setattr(helpers.Path, "home", classmethod(lambda cls: tmp_path / "home"))
        monkeypatch.setattr(helpers, "_discover_project_forge_root", lambda: None)

        assert resolve_root(None) == global_root.absolute()

    def test_auto_detect_finds_forge_root(self):
        # resolve_root(None) walks up from __file__ to find a dir containing
        # both registry/ and CLAUDE.md. Verify it actually found a valid forge
        # root — not just "some Path object" (the old assertions were tautological
        # and would pass for any Path). Note: this tests the REAL repo, so the
        # forge_root fixture is intentionally not used here.
        result = resolve_root(None)
        assert (result / "registry").is_dir()
        assert (result / "CLAUDE.md").is_file()


class TestClaudeRoot:
    def test_returns_parent(self, tmp_path):
        forge = tmp_path / "forge"
        forge.mkdir()
        result = claude_root_from_forge_root(forge)
        assert result == tmp_path


class TestPortablePath:
    def test_uses_source_prefix_for_repository_checkout(self, tmp_path):
        root = tmp_path / "project" / ".forge-skill" / "forge"
        target = root / "CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Forge", encoding="utf-8")

        assert portable_path_from_forge_root(root, target) == ".forge-skill/forge/CLAUDE.md"

    def test_uses_codex_prefix_for_a_codex_installation(self, tmp_path):
        root = tmp_path / "project" / ".codex" / "forge"
        target = root / "CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Forge", encoding="utf-8")

        assert portable_path_from_forge_root(root, target) == ".codex/forge/CLAUDE.md"

    def test_uses_relative_path_for_an_unscoped_root(self, tmp_path):
        root = tmp_path / "forge"
        target = root / "CLAUDE.md"
        target.parent.mkdir()
        target.write_text("# Forge", encoding="utf-8")

        assert portable_path_from_forge_root(root, target) == "./CLAUDE.md"


class TestResolveRegisteredPath:
    def test_claude_prefix(self, tmp_path):
        root = tmp_path / "forge"
        root.mkdir()
        (tmp_path / "skills").mkdir()
        expected = tmp_path / "skills" / "test.md"
        expected.write_text("test")
        result, error = resolve_registered_path(root, ".claude/skills/test.md")
        assert error is None
        assert result == expected.resolve()

    def test_codex_prefix(self, tmp_path):
        root = tmp_path / ".codex" / "forge"
        root.mkdir(parents=True)
        (root.parent / "skills").mkdir()
        expected = root.parent / "skills" / "test.md"
        expected.write_text("test")
        result, error = resolve_registered_path(root, ".codex/skills/test.md")
        assert error is None
        assert result == expected.resolve()

    def test_resolved_workspace_boundary_follows_a_forge_junction_target(self, tmp_path):
        logical_root = tmp_path / "consumer" / ".codex" / "forge"
        physical_root = tmp_path / "source" / ".claude" / "forge"
        physical_root.mkdir(parents=True)

        # A resolved root represents the physical target while the caller keeps
        # the logical path for host-facing paths.
        assert resolved_workspace_root_from_forge_root(physical_root) == physical_root.parent

    def test_relative_path(self, tmp_path):
        root = tmp_path / "forge"
        root.mkdir()
        expected = root / "test.md"
        expected.write_text("test")
        result, error = resolve_registered_path(root, "./test.md")
        assert error is None
        assert result == expected.resolve()

    @pytest.mark.parametrize(
        "value, code",
        [
            ("../../outside.md", "REGISTERED_PATH_ESCAPE"),
            (".claude/../../outside.md", "REGISTERED_PATH_ESCAPE"),
            ("/tmp/outside.md", "REGISTERED_PATH_ABSOLUTE"),
            (r"C:\\temp\\outside.md", "REGISTERED_PATH_ABSOLUTE"),
            (r"C:temp\\outside.md", "REGISTERED_PATH_ABSOLUTE"),
            (r"\\\\server\\share\\outside.md", "REGISTERED_PATH_ABSOLUTE"),
            ("", "REGISTERED_PATH_INVALID"),
            (None, "REGISTERED_PATH_INVALID"),
        ],
    )
    def test_rejects_invalid_or_escaping_path(self, tmp_path, value, code):
        root = tmp_path / "forge"
        root.mkdir()
        result, error = resolve_registered_path(root, value)
        assert result is None
        assert error["code"] == code

    def test_rejects_symlink_escape(self, tmp_path):
        root = tmp_path / "forge"
        root.mkdir()
        outside = tmp_path.parent / "outside.md"
        outside.write_text("outside")
        link = root / "external-link.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"symlink creation is unavailable: {exc}")

        result, error = resolve_registered_path(root, "external-link.md")
        assert result is None
        assert error["code"] == "REGISTERED_PATH_ESCAPE"


class TestLoadJson:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        data = load_json(f)
        assert data == {"key": "value"}

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nonexistent.json")

    def test_raises_on_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        with pytest.raises(json.JSONDecodeError):
            load_json(f)


class TestLoadJsonFileSafe:
    def test_success(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"a": 1}')
        data, err = load_json_file_safe(f)
        assert data == {"a": 1}
        assert err is None

    def test_failure_returns_error(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        data, err = load_json_file_safe(f)
        assert data is None
        assert err is not None


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Hello World") == "hello world"

    def test_collapse_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_chinese(self):
        assert normalize_text("帮我 Review 代码") == "帮我 review 代码"


class TestSafeNameToIdSuffix:
    def test_hyphen_replacement(self):
        assert safe_name_to_id_suffix("code-review") == "code_review"
        assert safe_name_to_id_suffix("test-design") == "test_design"

    def test_no_hyphen(self):
        assert safe_name_to_id_suffix("debug") == "debug"


class TestIsStringList:
    def test_valid(self):
        assert is_string_list(["a", "b", "c"]) is True

    def test_empty(self):
        assert is_string_list([]) is True

    def test_invalid_mixed(self):
        assert is_string_list(["a", 1, "c"]) is False

    def test_not_a_list(self):
        assert is_string_list("not a list") is False
        assert is_string_list(None) is False


class TestIsString2dList:
    def test_valid(self):
        assert is_string_2d_list([["a", "b"], ["c"]]) is True

    def test_invalid_nested(self):
        assert is_string_2d_list([["a", 1]]) is False

    def test_not_list(self):
        assert is_string_2d_list("not a list") is False
