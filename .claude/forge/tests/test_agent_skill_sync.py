import importlib.util
import json
import os
from pathlib import Path

import pytest

from forge_cli import agent_skill_sync
from forge_cli.agent_skill_sync import apply_sync, apply_uninstall, plan_sync, resolve_skills_root


def _source_root(tmp_path: Path) -> Path:
    source = tmp_path / ".claude"
    for name in ("alpha", "beta"):
        skill = source / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (source / "skills" / "notes").mkdir()
    return source


def _script_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "sync-agent-skills.py"
    spec = importlib.util.spec_from_file_location("sync_agent_skills", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("client", "expected"),
    [("codex", ".codex/skills"), ("claude", ".claude/skills"), ("cursor", ".cursor/skills")],
)
def test_global_roots_are_client_specific(tmp_path, client, expected):
    assert resolve_skills_root(client, "global", home=tmp_path).relative_to(tmp_path).as_posix() == expected


@pytest.mark.parametrize("client", ["codex", "claude", "cursor"])
def test_project_roots_are_client_specific(tmp_path, client):
    project = tmp_path / "project"
    project.mkdir()

    result = resolve_skills_root(client, "project", project=project)

    assert result == project / f".{client}" / "skills"


def test_project_scope_requires_existing_explicit_project(tmp_path):
    with pytest.raises(ValueError, match="project directory does not exist"):
        resolve_skills_root("claude", "project", project=tmp_path / "typo")


def test_plan_links_only_valid_skill_directories(tmp_path):
    source = _source_root(tmp_path)

    actions = plan_sync(source, tmp_path / "global-skills")

    assert [(action.name, action.status) for action in actions] == [("alpha", "create"), ("beta", "create")]


def test_apply_creates_only_missing_links_and_preserves_conflicts(tmp_path):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"
    (target / "alpha").mkdir(parents=True)
    made = []

    actions = apply_sync(source, target, create_link=lambda path, origin: made.append((path, origin)))

    assert [(action.name, action.status) for action in actions] == [("alpha", "conflict"), ("beta", "create")]
    assert made == [(target / "beta", source / "skills" / "beta")]


def test_apply_rolls_back_links_created_before_a_later_failure(tmp_path):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"

    def create_link(path, _origin):
        if path.name == "beta":
            raise OSError("link failed")
        path.mkdir(parents=True)

    with pytest.raises(OSError, match="link failed"):
        apply_sync(source, target, create_link=create_link)

    assert not (target / "alpha").exists()
    assert not (target / "beta").exists()


def test_apply_reports_residual_paths_when_rollback_fails(tmp_path):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"

    def create_link(path, _origin):
        if path.name == "beta":
            raise OSError("link failed")

    with pytest.raises(OSError, match="rollback failed for"):
        apply_sync(
            source,
            target,
            create_link=create_link,
            remove_link=lambda path: (_ for _ in ()).throw(OSError("busy")),
        )


def test_uninstall_removes_only_links_to_current_source(tmp_path, monkeypatch):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"
    (target / "alpha").mkdir(parents=True)
    (target / "beta").mkdir(parents=True)
    monkeypatch.setattr(agent_skill_sync, "_link_target", lambda path: source / "skills" / path.name if path.name == "alpha" else tmp_path / "other" / path.name)
    actions = apply_uninstall(source, target)

    assert actions[0].status == "remove"
    assert actions[1].status == "preserved"


def test_existing_correct_link_is_unchanged(tmp_path, monkeypatch):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"
    (target / "alpha").mkdir(parents=True)
    (target / "beta").mkdir(parents=True)
    monkeypatch.setattr(agent_skill_sync, "_link_target", lambda path: source / "skills" / path.name)

    actions = plan_sync(source, target)

    assert all(action.status == "unchanged" for action in actions)


@pytest.mark.skipif(os.name == "nt", reason="exercises the POSIX symlink implementation")
def test_posix_apply_creates_real_directory_symlinks_idempotently(tmp_path):
    source = _source_root(tmp_path)
    target = tmp_path / "global-skills"

    first = apply_sync(source, target)
    second = apply_sync(source, target)

    assert all(action.status == "create" for action in first)
    assert all((target / name).is_symlink() for name in ("alpha", "beta"))
    assert all(action.status == "unchanged" for action in second)


def test_cli_requires_project_for_project_scope():
    module = _script_module()

    with pytest.raises(SystemExit, match="--project is required"):
        module.main(["--client", "cursor", "--scope", "project", "--check"])


def test_json_render_includes_client_scope_and_root(tmp_path, capsys):
    module = _script_module()
    source = _source_root(tmp_path)
    target = tmp_path / "target"
    actions = plan_sync(source, target)

    module.render(actions, client="claude", scope="global", skills_root=target, as_json=True, verbose=False)

    output = json.loads(capsys.readouterr().out)
    assert output["client"] == "claude"
    assert output["scope"] == "global"
    assert output["skills_root"] == str(target)


def test_top_level_wrapper_uses_common_installer():
    wrapper = Path(__file__).resolve().parents[3] / "install-skills.bat"

    assert "sync-agent-skills.py" in wrapper.read_text(encoding="utf-8")


def test_cli_reports_sync_error_without_traceback(tmp_path, monkeypatch, capsys):
    module = _script_module()
    monkeypatch.setattr(module, "apply_sync", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("link failed")))

    result = module.main([
        "--client",
        "claude",
        "--scope",
        "global",
        "--target",
        str(tmp_path / "skills"),
    ])

    assert result == 1
    assert capsys.readouterr().err == "error: link failed\n"


def test_cli_uninstall_removes_current_source_links(tmp_path, monkeypatch):
    module = _script_module()
    source = _source_root(tmp_path)
    target = tmp_path / "target"
    monkeypatch.setattr(module, "project_source_root", lambda _root: source)

    assert module.main(["--client", "codex", "--scope", "global", "--target", str(target)]) == 0
    assert module.main(["--client", "codex", "--scope", "global", "--target", str(target), "--uninstall"]) == 0
    assert not (target / "alpha").exists()
    assert not (target / "beta").exists()
