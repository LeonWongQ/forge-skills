# -*- coding: utf-8 -*-
"""Tests for the public-source sensitive-content gate."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check-sensitive-content.py"
SPEC = importlib.util.spec_from_file_location("check_sensitive_content", SCRIPT_PATH)
check_sensitive_content = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_sensitive_content)


def test_repository_public_source_has_no_sensitive_content():
    assert check_sensitive_content.validate_tree()[1] == []


def test_realistic_secret_and_machine_path_are_rejected(tmp_path):
    target = tmp_path / "config.txt"
    github_token = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz123456"
    user_name = "ali" + "ce"
    target.write_text(
        f"token={github_token}\npath=C:\\Users\\{user_name}\\project\n",
        encoding="utf-8",
    )

    _, errors = check_sensitive_content.validate_tree(tmp_path)

    assert any("GitHub token" in error for error in errors)
    assert any("Windows user path" in error for error in errors)


def test_placeholders_and_local_artifacts_do_not_fail(tmp_path):
    (tmp_path / "guide.md").write_text("Use <TOKEN> from <ENV_NAME>.\n", encoding="utf-8")
    local = tmp_path / ".skill-eval"
    local.mkdir()
    local_token = "s" + "k-this-is-local-evaluation-output-12345"
    (local / "response.txt").write_text(f"{local_token}\n", encoding="utf-8")

    assert check_sensitive_content.validate_tree(tmp_path)[1] == []


def test_organization_person_and_email_identifiers_are_rejected(tmp_path):
    organization = "".join(chr(codepoint) for codepoint in (0x516C, 0x53F8))
    person = "".join(chr(codepoint) for codepoint in (0x5F20, 0x4E09))
    email = "person" + "@" + "example.test"
    (tmp_path / "public.md").write_text(
        f"{organization}\n{person}\n{email}\n",
        encoding="utf-8",
    )

    _, errors = check_sensitive_content.validate_tree(tmp_path)

    assert any("prohibited organization term" in error for error in errors)
    assert any("prohibited personal identifier" in error for error in errors)
    assert any("email address" in error for error in errors)


def test_non_utf8_public_file_fails_closed(tmp_path):
    target = tmp_path / "public.ps1"
    target.write_bytes("Write-Output 'content'\n".encode("utf-16"))

    _, errors = check_sensitive_content.validate_tree(tmp_path)

    assert any("not valid UTF-8" in error for error in errors)
