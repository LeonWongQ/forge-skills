#!/usr/bin/env python3
"""Validate UTF-8 and reject high-confidence text corruption in project files."""

from __future__ import annotations

import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".bat", ".css", ".html", ".js", ".json", ".md", ".mjs", ".ps1",
    ".py", ".sh", ".toml", ".ts", ".txt", ".yaml", ".yml",
}
EXCLUDED_PARTS = {".git", ".skill-eval", ".test-tmp", "__pycache__", "node_modules"}
MOJIBAKE_CODEPOINTS = (
    (0x9225, 0x003F),
    (0x922B, 0x003F),
    (0x93C2, 0x89C4, 0xE50D),
    (0x7039, 0x70B0, 0x5E7F),
    (0x7481, 0x6350, 0xE178),
    (0x951B, 0x003F),
    (0x9286, 0x003F),
    (0x9983,),
)
MOJIBAKE_FRAGMENTS = tuple("".join(chr(value) for value in codepoints) for codepoints in MOJIBAKE_CODEPOINTS)


def project_text_files(root: Path = TOOL_ROOT) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def validate_file(path: Path) -> list[str]:
    try:
        content = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        return [f"not valid UTF-8 at byte {error.start}"]
    errors = []
    if "\x00" in content:
        errors.append("contains NUL bytes")
    if "\ufffd" in content:
        errors.append("contains Unicode replacement characters")
    found = [fragment for fragment in MOJIBAKE_FRAGMENTS if fragment in content]
    if found:
        errors.append(f"contains likely mojibake fragment(s): {', '.join(repr(item) for item in found)}")
    return errors


def validate_tree(root: Path = TOOL_ROOT) -> tuple[int, list[str]]:
    files = project_text_files(root)
    errors = []
    for path in files:
        for error in validate_file(path):
            errors.append(f"{path.relative_to(root).as_posix()}: {error}")
    return len(files), errors


def main() -> int:
    count, errors = validate_tree()
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"Text integrity valid: {count} project-owned text files are strict UTF-8 with no known corruption markers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
