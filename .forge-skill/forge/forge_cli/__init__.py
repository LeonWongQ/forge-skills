# -*- coding: utf-8 -*-
"""forge_cli - modular AI Engineering Operating System CLI."""

__version__ = "1.1.1"
__all__ = ["main"]


def __getattr__(name: str):
    """Load the dependency-heavy Click entrypoint only when requested."""
    if name != "main":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from .cli import main

    return main
