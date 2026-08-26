# -*- coding: utf-8 -*-
"""Tests for project text encoding and corruption validation."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check-text-integrity.py"
SPEC = importlib.util.spec_from_file_location("check_text_integrity", SCRIPT_PATH)
check_text_integrity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_text_integrity)


def test_repository_text_is_valid_utf8_without_known_corruption():
    count, errors = check_text_integrity.validate_tree()

    assert count > 300
    assert errors == []


def test_invalid_utf8_is_rejected(tmp_path):
    path = tmp_path / "broken.md"
    path.write_bytes(b"valid prefix\xff")

    assert "not valid UTF-8" in check_text_integrity.validate_file(path)[0]


def test_replacement_character_and_nul_are_rejected(tmp_path):
    path = tmp_path / "broken.md"
    path.write_text("bad \ufffd\x00 text", encoding="utf-8")

    errors = check_text_integrity.validate_file(path)

    assert "contains NUL bytes" in errors
    assert "contains Unicode replacement characters" in errors


def test_known_mojibake_fragment_is_rejected(tmp_path):
    path = tmp_path / "broken.md"
    path.write_text("broken arrow: " + check_text_integrity.MOJIBAKE_FRAGMENTS[1], encoding="utf-8")

    assert any("likely mojibake" in error for error in check_text_integrity.validate_file(path))


def test_generated_and_dependency_directories_are_excluded(tmp_path):
    (tmp_path / "good.md").write_text("正常 UTF-8", encoding="utf-8")
    for directory in check_text_integrity.EXCLUDED_PARTS:
        target = tmp_path / directory / "ignored.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"\xff")

    files = check_text_integrity.project_text_files(tmp_path)

    assert files == [tmp_path / "good.md"]
