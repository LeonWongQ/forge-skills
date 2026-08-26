# -*- coding: utf-8 -*-
"""Personal Forge-link state and Claude Code hook ownership management."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .helpers import TOOL_CONFIG_DIRECTORIES


STATE_VERSION = "1.0"
HOOK_MARKER = "forge-personal-paused-runtime-advisory-v1"
HOOK_FILENAME = "forge-sessionstart-advisory.py"


def _state_root(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".claude" / "forge-link-forge"


def _installs_dir(home: Path | None = None) -> Path:
    return _state_root(home) / "installs"


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load_json(path: Path) -> tuple[dict[str, Any], bytes | None]:
    if not path.exists():
        return {}, None
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"settings 必须是 JSON 对象：{path}")
    return value, raw


def _manifest_path(install_id: str, home: Path | None = None) -> Path:
    return _installs_dir(home) / f"{install_id}.json"


def _normalized_path(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(path))))


def _restore_file_if_unchanged(path: Path, before: bytes | None, written: bytes) -> None:
    """Compensate a failed state update without overwriting a concurrent edit."""
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        if before is None:
            return
        raise OSError(f"cannot restore missing settings file: {path}") from None
    if current != written:
        raise OSError(f"settings changed after Forge wrote it: {path}")
    if before is None:
        path.unlink()
    else:
        _atomic_write(path, before)


def _restore_manifest_hook(manifest: dict[str, Any], had_hook: bool, previous_hook: Any) -> None:
    if had_hook:
        manifest["hook"] = previous_hook
    else:
        manifest.pop("hook", None)


def _save_manifest_after_settings_write(
    manifest: dict[str, Any],
    *,
    home: Path | None,
    settings_path: Path,
    settings_before: bytes | None,
    settings_written: bytes,
    had_hook: bool,
    previous_hook: Any,
) -> None:
    try:
        save_manifest(manifest, home)
    except BaseException as save_error:
        _restore_manifest_hook(manifest, had_hook, previous_hook)
        try:
            _restore_file_if_unchanged(settings_path, settings_before, settings_written)
        except BaseException as restore_error:
            raise OSError(
                f"manifest update failed ({save_error}); settings rollback failed "
                f"({restore_error}); inspect residual settings: {settings_path}"
            ) from restore_error
        raise


def create_manifest(
    *,
    project: Path,
    source_root: Path,
    tool: str,
    created_links: list[dict[str, str]],
    install_id: str | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    install_id = install_id or uuid.uuid4().hex
    manifest_path = _manifest_path(install_id, home)
    if manifest_path.exists():
        raise ValueError(f"installation record already exists: {install_id}")
    manifest = {
        "schema_version": STATE_VERSION,
        "install_id": install_id,
        "created_at": datetime.now(UTC).isoformat(),
        "project": str(project.resolve()),
        "source_root": str(source_root.resolve()),
        "tool": tool,
        "created_links": created_links,
        "hook": None,
        "status": "installed",
    }
    _atomic_write(manifest_path, _json_bytes(manifest))
    return manifest


def load_manifest(install_id: str, home: Path | None = None) -> dict[str, Any]:
    path = _manifest_path(install_id, home)
    value, _ = _load_json(path)
    if value.get("install_id") != install_id:
        raise ValueError("安装记录不匹配")
    return value


def save_manifest(manifest: dict[str, Any], home: Path | None = None) -> None:
    _atomic_write(_manifest_path(manifest["install_id"], home), _json_bytes(manifest))


def list_manifests(home: Path | None = None) -> list[dict[str, Any]]:
    directory = _installs_dir(home)
    if not directory.is_dir():
        return []
    results = []
    for path in sorted(directory.glob("*.json")):
        try:
            value, _ = _load_json(path)
            if value.get("schema_version") == STATE_VERSION and isinstance(value.get("install_id"), str):
                results.append(value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue
    return results


def _hook_entry(hook_script: Path) -> dict[str, Any]:
    command = f'python "{hook_script}" # {HOOK_MARKER}'
    return {"matcher": "*", "hooks": [{"type": "command", "command": command, "timeout": 10}]}


def _session_start_entries(settings: dict[str, Any], create: bool) -> list[Any]:
    hooks = settings.get("hooks")
    if hooks is None and create:
        hooks = {}
        settings["hooks"] = hooks
    if not isinstance(hooks, dict):
        raise ValueError("settings.hooks 必须是对象")
    entries = hooks.get("SessionStart")
    if entries is None and create:
        entries = []
        hooks["SessionStart"] = entries
    if not isinstance(entries, list):
        raise ValueError("settings.hooks.SessionStart 必须是数组")
    return entries


def install_hook(
    manifest: dict[str, Any], *, settings_path: Path, hook_script: Path, home: Path | None = None
) -> dict[str, Any]:
    settings, before = _load_json(settings_path)
    hook_path = hook_script.absolute()
    entry = _hook_entry(hook_path)
    entries = _session_start_entries(settings, create=True)
    marker_entries = [item for item in entries if HOOK_MARKER in json.dumps(item, ensure_ascii=False)]
    if marker_entries and marker_entries != [entry]:
        raise ValueError("发现内容不匹配的 Forge 提醒 Hook，拒绝覆盖")
    if not marker_entries:
        entries.append(entry)
    if not hook_path.is_file():
        raise ValueError(f"Hook 脚本不存在：{hook_path}")
    after = _json_bytes(settings)
    had_hook = "hook" in manifest
    previous_hook = manifest.get("hook")
    _atomic_write(settings_path, after)
    manifest["hook"] = {
        "settings_path": str(settings_path),
        "script_path": str(hook_path),
        "entry": entry,
        "before_digest": _digest_bytes(before) if before is not None else None,
        "after_digest": _digest_bytes(after),
    }
    _save_manifest_after_settings_write(
        manifest,
        home=home,
        settings_path=settings_path,
        settings_before=before,
        settings_written=after,
        had_hook=had_hook,
        previous_hook=previous_hook,
    )
    return manifest


def _other_hook_owners(manifest: dict[str, Any], home: Path | None) -> list[dict[str, Any]]:
    hook = manifest.get("hook", {})
    entry = hook.get("entry")
    settings_path = hook.get("settings_path")
    if not settings_path:
        return []
    return [
        item for item in list_manifests(home)
        if item.get("install_id") != manifest.get("install_id")
        and isinstance(item.get("hook"), dict)
        and item["hook"].get("settings_path")
        and _normalized_path(item["hook"]["settings_path"]) == _normalized_path(settings_path)
        and item["hook"].get("entry") == entry
    ]


def uninstall_hook(manifest: dict[str, Any], *, home: Path | None = None) -> str:
    hook = manifest.get("hook")
    if not isinstance(hook, dict):
        return "not-installed"
    if _other_hook_owners(manifest, home):
        manifest["hook"] = None
        try:
            save_manifest(manifest, home)
        except BaseException:
            manifest["hook"] = hook
            raise
        return "retained-for-other-installations"
    settings_path = Path(hook["settings_path"])
    settings, before = _load_json(settings_path)
    hooks = settings.get("hooks")
    if hooks is None:
        manifest["hook"] = None
        try:
            save_manifest(manifest, home)
        except BaseException:
            manifest["hook"] = hook
            raise
        return "already-absent"
    if not isinstance(hooks, dict):
        raise ValueError("settings.hooks 必须是对象")
    entries = hooks.get("SessionStart")
    if entries is None:
        manifest["hook"] = None
        try:
            save_manifest(manifest, home)
        except BaseException:
            manifest["hook"] = hook
            raise
        return "already-absent"
    if not isinstance(entries, list):
        raise ValueError("settings.hooks.SessionStart 必须是数组")
    entry = hook.get("entry")
    matches = [index for index, item in enumerate(entries) if item == entry]
    if len(matches) > 1:
        raise ValueError("发现多个相同 Forge Hook，无法安全卸载")
    after = None
    if matches:
        entries.pop(matches[0])
        hooks = settings["hooks"]
        if not entries:
            hooks.pop("SessionStart", None)
        if not hooks:
            settings.pop("hooks", None)
        after = _json_bytes(settings)
        _atomic_write(settings_path, after)
    manifest["hook"] = None
    if after is None:
        try:
            save_manifest(manifest, home)
        except BaseException:
            manifest["hook"] = hook
            raise
    else:
        _save_manifest_after_settings_write(
            manifest,
            home=home,
            settings_path=settings_path,
            settings_before=before,
            settings_written=after,
            had_hook=True,
            previous_hook=hook,
        )
    script_path = Path(hook["script_path"])
    legacy_global_script = script_path.parent == ((home or Path.home()) / ".claude" / "hooks")
    if legacy_global_script and script_path.is_file():
        try:
            script_path.unlink()
        except OSError:
            pass
    return "removed" if matches else "already-absent"


def uninstall_links(manifest: dict[str, Any], *, home: Path | None = None) -> dict[str, list[str]]:
    """Remove only manifest-owned Windows junctions still targeting recorded sources."""
    removed: list[str] = []
    skipped: list[str] = []
    if os.name != "nt":
        raise ValueError("Junction 卸载仅支持 Windows")
    from .deployment_verification import WindowsJunctionInspector, _normalized

    inspector = WindowsJunctionInspector()
    for link in manifest.get("created_links", []):
        if not isinstance(link, dict):
            continue
        path = Path(link.get("path", ""))
        source = Path(link.get("source", ""))
        inspected = inspector.inspect(path)
        if inspected.kind != "junction" or not inspected.target or _normalized(inspected.target) != _normalized(source):
            skipped.append(str(path))
            continue
        try:
            path.rmdir()
            removed.append(str(path))
        except OSError:
            skipped.append(str(path))
    if not skipped:
        manifest["status"] = "uninstalled"
    save_manifest(manifest, home)
    return {"removed": removed, "skipped": skipped}


def delete_manifest(manifest: dict[str, Any], home: Path | None = None) -> None:
    path = _manifest_path(manifest["install_id"], home)
    if path.exists():
        path.unlink()


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False))


def _confirm(prompt: str, reader=input) -> bool:
    return reader(prompt).strip().casefold() in {"y", "yes", "是", "确认"}


def _select_manifest(candidates: list[dict[str, Any]], reader=input) -> dict[str, Any] | None:
    if not candidates:
        print("没有可处理的项目安装记录。")
        return None
    print("\n请选择项目：")
    for index, manifest in enumerate(candidates, start=1):
        project = Path(manifest["project"])
        hook_state = "已开启" if isinstance(manifest.get("hook"), dict) else "未开启"
        print(f"{index}. {project.name}")
        print(f"   {project}")
        print(f"   工具：{manifest.get('tool')}；已创建链接：{len(manifest.get('created_links', []))}；启动提示：{hook_state}")
    selected = reader("请输入项目序号（留空取消）： ").strip()
    if not selected:
        print("[已取消] 未做任何修改。")
        return None
    if selected.isdigit() and 1 <= int(selected) <= len(candidates):
        return candidates[int(selected) - 1]
    matched = [item for item in candidates if item.get("install_id") == selected]
    if len(matched) == 1:
        return matched[0]
    print("[错误] 无效项目序号。")
    return None


def interactive_remove_hook(reader=input, home: Path | None = None) -> int:
    candidates = [item for item in list_manifests(home) if isinstance(item.get("hook"), dict)]
    manifest = _select_manifest(candidates, reader)
    if manifest is None:
        return 0
    project = Path(manifest["project"])
    config_directory = TOOL_CONFIG_DIRECTORIES.get(manifest.get("tool"), ".claude")
    print(f"\n将从以下项目移除 Forge 启动提示：\n- {project.name}\n- {project}\\{config_directory}\\settings.local.json")
    print("不会删除 Forge、Skills、项目文件、.forge\\runtime 或 .gitignore。")
    if not _confirm("确认移除本项目启动提示？[Y/N，默认 N]： ", reader):
        print("[已取消] 未做任何修改。")
        return 0
    try:
        result = uninstall_hook(load_manifest(manifest["install_id"], home), home=home)
        print(f"[完成] 启动提示处理结果：{result}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[失败] 无法安全移除启动提示：{error}")
        return 1


def _project_candidates(home: Path | None = None) -> list[dict[str, Any]]:
    """Return one newest installation record for each project path."""
    selected: dict[str, dict[str, Any]] = {}
    for manifest in sorted(list_manifests(home), key=lambda item: item.get("created_at", ""), reverse=True):
        selected.setdefault(os.path.normcase(manifest["project"]), manifest)
    return list(selected.values())


def interactive_uninstall_links(reader=input, home: Path | None = None) -> int:
    manifest = _select_manifest(_project_candidates(home), reader)
    if manifest is None:
        return 0
    project = Path(manifest["project"])
    config_directory = TOOL_CONFIG_DIRECTORIES.get(manifest.get("tool"), ".claude")
    related = [item for item in list_manifests(home) if os.path.normcase(item["project"]) == os.path.normcase(str(project))]
    links = [link for item in related for link in item.get("created_links", [])]
    unique_links = {link.get("path"): link for link in links if isinstance(link, dict) and link.get("path")}
    print(f"\n将完整卸载项目：{project.name}\n路径：{project}")
    print("将移除：")
    for link in unique_links.values():
        print(f"- {link.get('path')}")
    if any(isinstance(item.get("hook"), dict) for item in related):
        print(f"- 本项目 {config_directory}\\settings.local.json 中由 Forge 添加的启动提示")
    print("不会删除：项目目录、其他 settings 配置、.forge\\runtime、.gitignore。")
    if not _confirm("确认完整卸载该项目？[Y/N，默认 N]： ", reader):
        print("[已取消] 未做任何修改。")
        return 0
    try:
        for item in related:
            current = load_manifest(item["install_id"], home)
            uninstall_hook(current, home=home)
        merged = dict(manifest)
        merged["created_links"] = list(unique_links.values())
        link_result = uninstall_links(merged, home=home)
        if link_result["skipped"]:
            print("[提示] 以下链接无法安全删除，已保留安装记录：")
            for path in link_result["skipped"]:
                print(f"- {path}")
            return 1
        for item in related:
            delete_manifest(item, home)
        print("[完成] 已移除本项目的 Forge 链接和启动提示，并删除安装记录。")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[失败] 无法完成安全卸载，已保留安装记录：{error}")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="管理 Forge 本机安装记录和个人提醒 Hook")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-manifest")
    create.add_argument("--project", required=True, type=Path)
    create.add_argument("--source-root", required=True, type=Path)
    create.add_argument("--tool", required=True)
    create.add_argument("--links-json", default="[]")
    create.add_argument("--link", action="append", default=[])
    create.add_argument("--link-spec", action="append", default=[])
    create.add_argument("--install-id", default=None)
    install = subparsers.add_parser("install-hook")
    install.add_argument("--install-id", required=True)
    install.add_argument("--settings", required=True, type=Path)
    install.add_argument("--hook-script", required=True, type=Path)
    remove = subparsers.add_parser("remove-hook")
    remove.add_argument("--install-id", required=True)
    unlink = subparsers.add_parser("uninstall-links")
    unlink.add_argument("--install-id", required=True)
    subparsers.add_parser("interactive-uninstall-links")
    subparsers.add_parser("list")
    args = parser.parse_args(argv)
    try:
        if args.command == "create-manifest":
            links = json.loads(args.links_json)
            for encoded_link in args.link:
                links.append(json.loads(encoded_link))
            for link_spec in args.link_spec:
                name, path, source = link_spec.split("|", 2)
                links.append({"name": name, "path": path, "source": source})
            _print(create_manifest(project=args.project, source_root=args.source_root, tool=args.tool, created_links=links, install_id=args.install_id))
        elif args.command == "install-hook":
            _print(install_hook(load_manifest(args.install_id), settings_path=args.settings, hook_script=args.hook_script))
        elif args.command == "remove-hook":
            manifest = load_manifest(args.install_id)
            _print({"install_id": args.install_id, "result": uninstall_hook(manifest)})
        elif args.command == "uninstall-links":
            manifest = load_manifest(args.install_id)
            _print({"install_id": args.install_id, **uninstall_links(manifest)})
        elif args.command == "interactive-uninstall-links":
            return interactive_uninstall_links()
        else:
            _print(list_manifests())
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[错误] {error}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
