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


def resolve_timesheet(service, timesheet: Optional[str], on: Optional[str]) -> Dict[str, Any]:
    """The timesheet a command works on: --timesheet NAME, else the one covering --date (default today)."""
    from datetime import date

    from src.core import dates

    if timesheet and on:
        raise CliError("Use either --timesheet or --date, not both.", USAGE)
    if timesheet:
        return fetch_timesheet(service, timesheet)
    try:
        day = dates.parse_date(on) if on else date.today()
    except ValueError as exc:
        raise CliError(f"--date: {exc}", USAGE)
    return load_timesheet_for_day(service, day.isoformat())


def pick_entry(detail: Dict[str, Any], ref: str) -> Dict[str, Any]:
    """Find an entry by its number in `log list` (the # column), by 'last', or by internal id."""
    from src.cli.errors import ERROR

    rows = detail.get("time_logs") or []
    if not rows:
        raise CliError(f"{detail.get('name')} has no entries.", ERROR)
    wanted = (ref or "").strip().lower()
    if wanted == "last":
        return rows[-1]
    if wanted.isdigit():
        matches = [r for r in rows if str(r.get("idx")) == str(int(wanted))]
    else:
        matches = [r for r in rows if str(r.get("name", "")).lower() == wanted]
    if not matches:
        raise CliError(
            f"No entry '{ref}' in {detail.get('name')} (it has entries 1 to {len(rows)}).", USAGE,
            hint="Use `samta-tracker log list` to see the numbers.",
        )
    return matches[0]


def is_interactive() -> bool:
    """True when a person can answer prompts (stdin is a terminal)."""
    return sys.stdin.isatty()


def require_yes_or_terminal(opts, what: str) -> bool:
    """For destructive commands: True if we may ask in a terminal, False if -y was given.

    Without -y and without a terminal there is nobody to confirm, so refuse.
    """
    if opts.yes:
        return False
    if not is_interactive():
        raise CliError(f"{what} needs confirmation. Run it in a terminal, or pass -y.", USAGE)
    return True


def fetch_timesheet(service, name: str) -> Dict[str, Any]:
    """get_timesheet_detail, but a missing timesheet gives a plain "not found" message."""
    from src.services.timesheet_shared import TimesheetServiceError

    try:
        return service.get_timesheet_detail(name.strip())
    except TimesheetServiceError as exc:
        if "missing docs" in str(exc):
            raise CliError(f"Timesheet '{name.strip()}' was not found.", USAGE,
                           hint="Use `samta-tracker timesheets list` to see your timesheets.")
        raise
