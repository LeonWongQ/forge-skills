#!/usr/bin/env python3
"""Reject high-confidence secrets and machine-specific data from public source files."""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TEXT_SUFFIXES = {
    "", ".bat", ".cfg", ".css", ".html", ".ini", ".js", ".json",
    ".md", ".mjs", ".ps1", ".py", ".sh", ".toml", ".ts", ".txt",
    ".yaml", ".yml",
}
EXCLUDED_PARTS = {
    ".git", ".skill-eval", ".test-tmp", ".pytest_cache", "__pycache__",
    "node_modules", "out",
}
EXCLUDED_FILES = {
    ".claude/settings.local.json",
    ".cursor/settings.local.json",
}
FORGE_DATA_PUBLIC_FILES = {
    ".forge-skill/forge-data/.gitignore",
    ".forge-skill/forge-data/README.md",
}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private IPv4 address": re.compile(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
        r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
    ),
    "Windows user path": re.compile(r"\b[A-Za-z]:[\\/]Users[\\/][^\\/\s'\"]+", re.IGNORECASE),
    "POSIX user path": re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^/\s'\"]+"),
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "prohibited organization term": re.compile(
        "|".join(
            "".join(chr(codepoint) for codepoint in term)
            for term in (
                (0x56FD, 0x7F51),
                (0x7535, 0x7F51),
                (0x5357, 0x7F51),
                (0x516C, 0x53F8),
                (0x6717, 0x65B0),
            )
        )
    ),
    "prohibited personal identifier": re.compile(
        "|".join(
            (
                "".join(chr(codepoint) for codepoint in (0x5F20, 0x4E09)),
                "".join(chr(codepoint) for codepoint in (0x674E, 0x56DB)),
                "".join(chr(codepoint) for codepoint in (0x738B, 0x4E94)),
                "ls" + "LinQiang" + "Wang",
            )
        ),
        re.IGNORECASE,
    ),
    "prohibited example person name": re.compile(
        r"\b(?:" + "|".join(("Al" + "ex", "Ja" + "mie", "Ali" + "ce", "B" + "ob", "Jo" + "hn", "Ja" + "ne")) + r")\b",
        re.IGNORECASE,
    ),
}


def public_text_files(root: Path = REPO_ROOT) -> list[Path]:
    files = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames
            if name not in EXCLUDED_PARTS and not name.startswith(".pytest-")
        ]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if relative.as_posix() in EXCLUDED_FILES:
                continue
            if (relative.parts[:2] == (".forge-skill", "forge-data")
                    and relative.as_posix() not in FORGE_DATA_PUBLIC_FILES):
                continue
            files.append(path)
    return sorted(files)


def validate_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError:
        return ["file is not valid UTF-8 and could not be scanned"]
    except OSError as error:
        return [f"file could not be scanned: {type(error).__name__}"]
    findings = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(f"line {line_number}: contains {label}")
    return findings


def validate_tree(root: Path = REPO_ROOT) -> tuple[int, list[str]]:
    files = public_text_files(root)
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
    print(f"Sensitive-content check passed for {count} public source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
