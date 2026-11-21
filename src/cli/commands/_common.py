"""Pieces shared by the read commands: paging options and list rendering."""

import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

import typer

from src.cli.errors import USAGE, CliError
from src.cli.output import Column, GlobalOptions, emit_data
from src.core import paging
from src.core.paging import MAX_LIMIT, Fetch

LIMIT_OPTION = typer.Option(
    None, "-n", "--limit", min=1, max=MAX_LIMIT,
    help=f"Rows per page (default {paging.DEFAULT_PAGE_SIZE}); with --all, the most rows to fetch (default {paging.DEFAULT_ALL_LIMIT}).",
)
PAGE_OPTION = typer.Option(1, "--page", min=1, help="Page number.")
ALL_OPTION = typer.Option(False, "--all", help=f"Fetch every page, up to --limit rows (default {paging.DEFAULT_ALL_LIMIT}).")
SEARCH_OPTION = typer.Option(None, "-s", "--search", help="Search text.")


def run_list(
    ctx: typer.Context,
    fetch: Fetch,
    columns: Sequence[Column],
    noun: str,
    quiet_key: str,
    limit: Optional[int],
    page: int,
    all_pages: bool,
    post_filter: Optional[Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]] = None,
) -> None:
    """Fetch (paged), optionally filter, and print a list command's result."""
    opts: GlobalOptions = ctx.obj
    if all_pages and page != 1:
        raise CliError("--all cannot be combined with --page.", USAGE)

    result = paging.collect(fetch, limit, page, all_pages)
    if post_filter:
        result.rows = post_filter(result.rows)

    if not result.rows and not opts.json_mode:
        if not opts.quiet:
            print(f"No {noun} found.", file=sys.stderr)
        return
    emit_data(result.rows, columns, opts, footer=paging.footer(result, noun), quiet_key=quiet_key)
