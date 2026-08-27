"""Tests for canonical repository and client path definitions."""

from forge_cli.paths import (
    CLIENT_DIRECTORIES,
    FORGE_DIRECTORY,
    SKILLS_DIRECTORY,
    SOURCE_CONTAINER,
    client_skills_root,
    forge_source_root,
    repository_source_root,
    skills_source_root,
)


def test_repository_paths_share_one_source_container(tmp_path):
    source = repository_source_root(tmp_path)

    assert source == tmp_path / SOURCE_CONTAINER
    assert forge_source_root(tmp_path) == source / FORGE_DIRECTORY
    assert skills_source_root(tmp_path) == source / SKILLS_DIRECTORY


def test_client_paths_are_separate_from_repository_source(tmp_path):
    assert CLIENT_DIRECTORIES == {
        "claude": ".claude",
        "codex": ".codex",
        "cursor": ".cursor",
    }
    for client, directory in CLIENT_DIRECTORIES.items():
        assert client_skills_root(tmp_path, client) == tmp_path / directory / SKILLS_DIRECTORY
        assert directory != SOURCE_CONTAINER


def test_unknown_client_is_rejected(tmp_path):
    try:
        client_skills_root(tmp_path, "unknown")
    except ValueError as error:
        assert str(error) == "unsupported client: unknown"
    else:
        raise AssertionError("unknown client should be rejected")
