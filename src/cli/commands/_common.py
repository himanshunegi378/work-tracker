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


def load_timesheet_for_day(service, iso_day: str) -> Dict[str, Any]:
    """Return the detail of the timesheet whose range covers `iso_day`."""
    from src.cli.errors import ERROR

    found = service.get_timesheets(page_length=1, covering_date=iso_day)
    if not found:
        raise CliError(
            f"No timesheet covers {iso_day}.", ERROR,
            hint="Use `samta-tracker timesheets list` to see your timesheets.",
        )
    return service.get_timesheet_detail(found[0]["name"])


def logs_on_day(detail: Dict[str, Any], iso_day: str) -> List[Dict[str, Any]]:
    """The detail's time-log rows that start on `iso_day`."""
    return [log for log in detail.get("time_logs") or [] if str(log.get("from_time") or "").startswith(iso_day)]


def day_total_hours(detail: Dict[str, Any], iso_day: str) -> float:
    """Hours logged on `iso_day`.

    Row hours are stored rounded to 2 decimals by the server, while the
    timesheet total is exact; a one-day timesheet's total is therefore better.
    """
    if str(detail.get("start_date")) == iso_day == str(detail.get("end_date")) and detail.get("total_hours") is not None:
        return float(detail["total_hours"])
    return sum(float(log.get("hours") or 0) for log in logs_on_day(detail, iso_day))
