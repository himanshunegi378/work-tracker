"""Lazy access to the shared AppContext from CLI commands."""

from typing import Optional

import typer

from src.core.app import AppContext, build_app


def get_context(ctx: typer.Context, base_url: Optional[str] = None) -> AppContext:
    """Build the shared AppContext on first use (keeps `--help` instant)."""
    state = ctx.find_root().meta
    if "app_ctx" not in state:
        state["app_ctx"] = build_app(base_url)
    return state["app_ctx"]
