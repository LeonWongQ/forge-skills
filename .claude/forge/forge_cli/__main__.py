# -*- coding: utf-8 -*-
"""Allow `python -m forge_cli` to execute the CLI.

The package is normally invoked via the `forge` console-script (see
pyproject.toml `[project.scripts]`) or via the backward-compatible
`.claude/skills/forge/forge.py` shim. This `__main__.py` makes
`python -m forge_cli` work directly, which is what scripts/check-route-regression.py
relies on.
"""

from .cli import main

raise SystemExit(main())
