# -*- coding: utf-8 -*-
"""UTF-8 interactive installer for Windows Forge junction deployments."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

from .deployment_verification import expected_links, verify_deployment
from .personal_hook_state import create_manifest


TOOL_LABELS = {"claude": "Claude Code", "cursor": "Cursor", "codex": "Code X"}
YES_ANSWERS = {"y", "yes", "是", "确认"}


def _print(message: str = "") -> None:
    print(message, flush=True)


def _confirm(prompt: str, reader: Callable[[str], str] = input) -> bool:
    return reader(prompt).strip().casefold() in YES_ANSWERS


def _trim_path(value: str) -> str:
    return value.strip(" ").strip('"').strip(" ")


def _source_claude(script_root: Path) -> Path:
    source = script_root / ".claude"
    if not (source / "forge").is_dir() or not (source / "skills").is_dir():
        raise ValueError(f"未找到 Forge 源目录：{source}")
    return source.resolve()


def _is_windows() -> bool:
    return os.name == "nt"


def _create_junction(path: Path, source: Path) -> None:
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(path), str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        detail = (completed.stdout + completed.stderr).strip()
        raise OSError(detail or f"无法创建 Junction：{path}")


def _remove_junction(path: Path) -> None:
    path.rmdir()


def _existing_link_target(path: Path) -> Path | None:
    try:
        target = os.readlink(path)
    except OSError:
        return None
    target_path = Path(target)
    return target_path if target_path.is_absolute() else path.parent / target_path


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(left.resolve(strict=False)))) == os.path.normcase(os.path.normpath(str(right.resolve(strict=False))))


def create_links(
    project: Path,
    tool: str,
    source_claude: Path,
    *,
    create_junction: Callable[[Path, Path], None] = _create_junction,
    remove_junction: Callable[[Path], None] = _remove_junction,
) -> tuple[list[dict[str, str]], list[str]]:
    """Create missing links only; return owned links and skipped link names."""
    if not _is_windows():
        raise ValueError("Forge Junction 安装仅支持 Windows")
    created: list[dict[str, str]] = []
    skipped: list[str] = []
    try:
        for item in expected_links(project, tool, source_claude):
            path = item["path"]
            source = item["source"]
            if not item["required"]:
                skipped.append(item["name"])
                _print(f"[{item['name']}] 未找到可选源目录，已跳过。")
                continue
            if path.exists() or path.is_symlink():
                target = _existing_link_target(path)
                if target is not None and _same_path(target, source):
                    skipped.append(item["name"])
                    _print(f"[{item['name']}] Junction 已存在，已跳过。")
                    continue
                raise ValueError(f"[{item['name']}] 已存在真实目录、文件或错误 Junction：{path}")
            create_junction(path, source)
            created.append({"name": item["name"], "path": str(path), "source": str(source)})
            _print(f"[{item['name']}] 已创建 Junction -> {source}")
    except BaseException as error:
        rollback_errors = []
        for item in reversed(created):
            path = Path(item["path"])
            try:
                remove_junction(path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            raise OSError(f"{error}; 回滚失败：{'; '.join(rollback_errors)}") from error
        raise
    return created, skipped


def _rollback_created_links(
    created: list[dict[str, str]],
    remove_junction: Callable[[Path], None],
) -> list[str]:
    errors = []
    for item in reversed(created):
        path = Path(item["path"])
        try:
            remove_junction(path)
        except OSError as error:
            errors.append(f"{path}: {error}")
    return errors


def _render_verification(result: dict[str, Any]) -> None:
    _print("\n正在验证 Junction 目标：")
    for item in result.get("items", []):
        _print(f"  [{item['status'].upper()}] {item['name']} {item['code']}")


def install(
    project: Path,
    tool: str,
    script_root: Path,
    *,
    offer_hook: bool,
    reader: Callable[[str], str] = input,
    create_junction: Callable[[Path, Path], None] = _create_junction,
    remove_junction: Callable[[Path], None] = _remove_junction,
) -> int:
    created: list[dict[str, str]] = []
    committed = False
    try:
        source_claude = _source_claude(script_root)
        target = project.resolve(strict=False)
        if not target.exists():
            if not _confirm(f'路径不存在："{target}"。是否创建该目录？[Y/N，默认 N]： ', reader):
                _print("[已取消] 未做任何修改。")
                return 0
            target.mkdir(parents=True)
        config = target / {"claude": ".claude", "cursor": ".cursor", "codex": ".codex"}[tool]
        config.mkdir(parents=True, exist_ok=True)
        _print("\n============================================================")
        _print(f"  {TOOL_LABELS[tool]} -- Forge 链接安装")
        _print(f"  目标项目：{target}")
        _print("============================================================")
        created, skipped = create_links(
            target,
            tool,
            source_claude,
            create_junction=create_junction,
            remove_junction=remove_junction,
        )
        verification = verify_deployment(target, tool, source_claude)
        _render_verification(verification)
        if not verification["ok"]:
            rollback_errors = _rollback_created_links(created, remove_junction)
            if rollback_errors:
                _print(f"[失败] Junction 验证未通过，且回滚失败：{'; '.join(rollback_errors)}")
            else:
                _print("[失败] Junction 验证未通过；本次创建的 Junction 已回滚。")
            return 1
        manifest = create_manifest(project=target, source_root=source_claude, tool=tool, created_links=created)
        committed = True
        _print(f"\n[验证通过] 创建 {len(created)} 个 Junction，跳过 {len(skipped)} 个。")
        _print(f"安装记录 ID：{manifest['install_id']}")
        _print("跨会话 Forge Runtime 可在需要时由 Claude 主动检查当前项目 .forge\\runtime。")
        _print("[完成] Forge 链接安装成功。")
        return 0
    except (OSError, ValueError) as error:
        rollback_errors = _rollback_created_links(created, remove_junction) if not committed else []
        if rollback_errors:
            _print(f"[失败] {error}；回滚失败：{'; '.join(rollback_errors)}")
            return 1
        _print(f"[失败] {error}")
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge Windows Junction 安装器")
    parser.add_argument("target", nargs="?", type=Path, help="目标项目路径")
    parser.add_argument("--tool", choices=tuple(TOOL_LABELS), default="claude")
    parser.add_argument("--no-hook-prompt", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    target = args.target
    if target is None:
        _print("============================================================")
        _print("  Forge 链接安装工具已启动")
        _print("============================================================")
        raw = _trim_path(input("目标项目路径（例如 D:\\my-project）： "))
        if not raw:
            _print("[失败] 未输入目标项目路径。")
            return 1
        target = Path(raw)
        choice = input("选择目标工具 [1 Claude Code / 2 Cursor / 3 Code X，默认 1]： ").strip() or "1"
        mapping = {"1": "claude", "2": "cursor", "3": "codex"}
        if choice not in mapping:
            _print("[失败] 无效工具选择。")
            return 1
        args.tool = mapping[choice]
    return install(target, args.tool, Path(__file__).resolve().parents[3], offer_hook=not args.no_hook_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
