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

# Keep the caller's logical path when this file is reached through a Windows
# Junction such as .codex/skills/forge. Python may resolve __file__ to the
# shared source checkout, but sys.argv[0] preserves the script path supplied
# by the caller. Fall back to __file__ for import-based execution.
_script_path = Path(sys.argv[0]) if Path(sys.argv[0]).name == "forge.py" else Path(__file__)
_tool_root = _script_path.absolute().parents[2]
_forge_root = _tool_root / "forge"
if not (_forge_root / "forge_cli").is_dir():
    raise SystemExit(f"Linked Forge root is unavailable: {_forge_root}")
if str(_forge_root) not in sys.path:
    sys.path.insert(0, str(_forge_root))

from forge_cli.cli import main

if __name__ == "__main__":
    main()
