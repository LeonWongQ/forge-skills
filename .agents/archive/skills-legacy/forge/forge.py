#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backward-compatible entry point for Forge CLI.
Delegates to forge_cli package.

Usage unchanged:  python forge.py <command>
New usage:        python -m forge_cli <command>
"""

import sys
from pathlib import Path

# forge.py is at .claude/skills/forge/forge.py
# forge_cli package is at .claude/forge/forge_cli/
# parents[0] = .claude/skills/forge/
# parents[1] = .claude/skills/
# parents[2] = .claude/
_forge_root = Path(__file__).resolve().parents[2] / "forge"
if not (_forge_root / "forge_cli").is_dir():
    raise SystemExit(f"Linked Forge root is unavailable: {_forge_root}")
if str(_forge_root) not in sys.path:
    sys.path.insert(0, str(_forge_root))

from forge_cli.cli import main

if __name__ == "__main__":
    main()
