# -*- coding: utf-8 -*-
"""Tests for interactive project selection during complete Forge removal."""

from forge_cli.personal_hook_state import _select_manifest, create_manifest, delete_manifest, load_manifest


def test_project_selector_accepts_display_number(tmp_path):
    home = tmp_path / "home"
    first = create_manifest(project=tmp_path / "first-project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)
    second = create_manifest(project=tmp_path / "second-project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    selected = _select_manifest([first, second], reader=lambda _: "2")

    assert selected is not None
    assert selected["project"].endswith("second-project")


def test_empty_project_selection_does_not_choose_manifest(tmp_path):
    home = tmp_path / "home"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    assert _select_manifest([manifest], reader=lambda _: "") is None
    assert load_manifest(manifest["install_id"], home)["install_id"] == manifest["install_id"]


def test_manifest_is_removed_only_after_safe_complete_uninstall(tmp_path):
    home = tmp_path / "home"
    manifest = create_manifest(project=tmp_path / "project", source_root=tmp_path / "source", tool="claude", created_links=[], home=home)

    delete_manifest(manifest, home)

    assert not (home / ".claude" / "forge-link-forge" / "installs" / f"{manifest['install_id']}.json").exists()
