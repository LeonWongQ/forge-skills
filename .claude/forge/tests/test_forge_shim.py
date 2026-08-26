# -*- coding: utf-8 -*-
"""Regression coverage for the linked-project Forge shim."""

import runpy
import sys
from pathlib import Path


def test_shim_keeps_the_logical_codex_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    codex = project / ".codex"
    forge = codex / "forge"
    skills = codex / "skills" / "forge"
    forge.mkdir(parents=True)
    skills.mkdir(parents=True)
    package = forge / "forge_cli"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("def main():\n    return None\n", encoding="utf-8")
    shim = skills / "forge.py"
    source = Path(__file__).resolve().parents[2] / "skills" / "forge" / "forge.py"
    shim.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(shim)])
    module = runpy.run_path(str(shim), run_name="forge_shim_test")

    assert module["_forge_root"] == forge.absolute()
