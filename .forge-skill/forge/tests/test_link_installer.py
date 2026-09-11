# -*- coding: utf-8 -*-
"""Tests for UTF-8 Python installer orchestration helpers."""

from pathlib import Path

import pytest

from forge_cli import link_installer


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "forge-source"
    for name in ("forge", "skills", "rules", "forge-data"):
        (root / ".claude" / name).mkdir(parents=True, exist_ok=True)
    return root / ".claude"


def test_trim_path_removes_outer_spaces_and_quotes():
    assert link_installer._trim_path('  "D:\\含空格 项目"  ') == "D:\\含空格 项目"
    assert link_installer._trim_path("   ") == ""


def test_create_links_creates_forge_and_skills_without_shell_serialization(tmp_path, monkeypatch):
    source = _source(tmp_path)
    project = tmp_path / "项目 & bang!"
    (project / ".claude").mkdir(parents=True)
    monkeypatch.setattr(link_installer, "_is_windows", lambda: True)

    made = []

    def create_link(path, target):
        made.append((path, target))

    created, skipped = link_installer.create_links(project, "claude", source, create_junction=create_link)

    assert [item["name"] for item in created] == ["forge", "skills", "forge-data"]
    assert skipped == []
    assert [item[0].name for item in made] == ["forge", "skills", "forge-data"]


def test_existing_real_directory_is_never_overwritten(tmp_path, monkeypatch):
    source = _source(tmp_path)
    project = tmp_path / "project"
    (project / ".claude" / "forge").mkdir(parents=True)
    monkeypatch.setattr(link_installer, "_is_windows", lambda: True)

    with pytest.raises(ValueError, match="真实目录"):
        link_installer.create_links(project, "claude", source, create_junction=lambda *_: None)


def test_create_links_rolls_back_earlier_junction_when_later_creation_fails(tmp_path, monkeypatch):
    source = _source(tmp_path)
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    monkeypatch.setattr(link_installer, "_is_windows", lambda: True)

    def create_link(path, _target):
        if path.name == "skills":
            raise OSError("junction failed")
        path.mkdir()

    with pytest.raises(OSError, match="junction failed"):
        link_installer.create_links(project, "claude", source, create_junction=create_link)

    assert not (project / ".claude" / "forge").exists()
    assert not (project / ".claude" / "skills").exists()


@pytest.mark.parametrize("failure", ["verification", "manifest"])
def test_install_rolls_back_links_when_post_creation_step_fails(tmp_path, monkeypatch, failure):
    source = _source(tmp_path)
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    monkeypatch.setattr(link_installer, "_is_windows", lambda: True)

    def create_link(path, _target):
        path.mkdir()

    if failure == "verification":
        monkeypatch.setattr(link_installer, "verify_deployment", lambda *_: {"ok": False, "items": []})
    else:
        monkeypatch.setattr(link_installer, "verify_deployment", lambda *_: {"ok": True, "items": []})
        monkeypatch.setattr(
            link_installer,
            "create_manifest",
            lambda **_: (_ for _ in ()).throw(OSError("manifest failed")),
        )

    result = link_installer.install(
        project,
        "claude",
        source.parent,
        offer_hook=False,
        create_junction=create_link,
    )

    assert result == 1
    assert not (project / ".claude" / "forge").exists()
    assert not (project / ".claude" / "skills").exists()
