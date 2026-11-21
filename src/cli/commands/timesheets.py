"""`samta-tracker timesheets list | view | today`."""

import json
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

import typer

from src.cli.commands._common import ALL_OPTION, LIMIT_OPTION, PAGE_OPTION, run_list
from src.cli.context import get_context
from src.cli.errors import ERROR, USAGE, CliError, handle_errors
from src.cli.output import GlobalOptions, emit_data, render_details
from src.core import dates

timesheets_app = typer.Typer(help="List and inspect timesheets.", no_args_is_help=True)


class Status(str, Enum):
    draft = "draft"
    submitted = "submitted"
    billed = "billed"
    payslip = "payslip"
    completed = "completed"
    cancelled = "cancelled"


_DATE_HELP = dates.HELP
_LOG_COLUMNS = [
    ("activity_type", "ACTIVITY"), ("project_name", "PROJECT"), ("from_time", "FROM"),
    ("to_time", "TO"), ("hours", "HOURS"), ("is_billable", "BILLABLE"), ("description", "DESCRIPTION"),
]
NO_LOGS_OPTION = typer.Option(False, "--no-logs", help="Hide the time-log rows.")


def _parse_date_option(value: Optional[str], flag: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return dates.parse_date(value)
    except ValueError as exc:
        raise CliError(f"{flag}: {exc}", USAGE)


def _log_rows(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tidy time-log rows for display (minutes precision, yes/no billable)."""
    rows = []
    for log in logs:
        row = dict(log)
        row["project_name"] = log.get("project_name") or log.get("project")
        for key in ("from_time", "to_time"):
            row[key] = str(log.get(key) or "")[:16] or None
        hours = log.get("hours")
        row["hours"] = round(float(hours), 2) if hours not in (None, "") else None
        row["is_billable"] = bool(log.get("is_billable"))
        rows.append(row)
    return rows


def _print_timesheet(detail: Dict[str, Any], opts: GlobalOptions, logs: Optional[List[Dict[str, Any]]], extra=()) -> None:
    amount = detail.get("total_billable_amount")
    currency = detail.get("currency") or ""
    print(render_details(
        [
            ("Timesheet", detail.get("name")), ("Status", detail.get("status")),
            ("Workflow", detail.get("workflow_state")), ("Employee", detail.get("employee_name")),
            ("Department", detail.get("department")), ("Company", detail.get("company")),
            ("Period", f"{detail.get('start_date') or '-'} → {detail.get('end_date') or '-'}"),
            ("Total hours", detail.get("total_hours")), ("Billable hours", detail.get("total_billable_hours")),
            ("Billable amount", f"{amount} {currency}".strip() if amount not in (None, "") else None),
            *extra,
        ],
        opts.color,
    ))
    if logs is not None:
        print()
        if logs:
            emit_data(_log_rows(logs), _LOG_COLUMNS, opts)
        else:
            print("No time logs.")


@timesheets_app.command("list")
@handle_errors
def list_(
    ctx: typer.Context,
    status: Optional[Status] = typer.Option(None, "--status", help="Only timesheets with this status."),
    workflow_state: Optional[str] = typer.Option(None, "--workflow-state", help="Exact workflow state, e.g. Approved."),
    from_: Optional[str] = typer.Option(None, "--from", help=f"Starting on or after this date ({_DATE_HELP})."),
    to: Optional[str] = typer.Option(None, "--to", help=f"Ending on or before this date ({_DATE_HELP})."),
    employee: Optional[str] = typer.Option(None, "--employee", help="Employee id (default: you)."),
    limit: Optional[int] = LIMIT_OPTION,
    page: int = PAGE_OPTION,
    all_pages: bool = ALL_OPTION,
) -> None:
    """List your timesheets, newest first."""
    from_date = _parse_date_option(from_, "--from")
    to_date = _parse_date_option(to, "--to")
    if from_date and to_date and from_date > to_date:
        raise CliError("--from is after --to.", USAGE)
    service = get_context(ctx).timesheets

    def fetch(start: int, count: int):
        return service.get_timesheets(
            start=start, page_length=count, employee=employee,
            status=status.value.capitalize() if status else None,
            workflow_state=workflow_state, from_date=from_date, to_date=to_date,
        )

    run_list(
        ctx, fetch,
        [("name", "NAME"), ("status", "STATUS"), ("workflow_state", "WORKFLOW"), ("start_date", "START"),
         ("end_date", "END"), ("total_hours", "HOURS")],
        noun="timesheets", quiet_key="name", limit=limit, page=page, all_pages=all_pages,
    )


@timesheets_app.command("view")
@handle_errors
def view(
    ctx: typer.Context,
    name: str = typer.Argument(..., metavar="NAME", help="Timesheet name, e.g. TS-2026-00418."),
    no_logs: bool = NO_LOGS_OPTION,
) -> None:
    """Show one timesheet with its time logs."""
    opts: GlobalOptions = ctx.obj
    detail = get_context(ctx).timesheets.get_timesheet_detail(name.strip())
    if opts.json_mode:
        print(json.dumps(detail, indent=2, ensure_ascii=False, default=str))
        return
    _print_timesheet(detail, opts, None if no_logs else detail.get("time_logs") or [])


@timesheets_app.command("today")
@handle_errors
def today(
    ctx: typer.Context,
    on: Optional[str] = typer.Option(None, "--date", help=f"Another day instead of today ({_DATE_HELP})."),
    no_logs: bool = NO_LOGS_OPTION,
) -> None:
    """Show the timesheet covering today, with that day's time logs."""
    opts: GlobalOptions = ctx.obj
    day = _parse_date_option(on, "--date") or date.today()
    iso = day.isoformat()
    service = get_context(ctx).timesheets

    found = service.get_timesheets(page_length=1, covering_date=iso)
    if not found:
        raise CliError(f"No timesheet covers {iso}.", ERROR, hint="Use `samta-tracker timesheets list` to see your timesheets.")
    detail = service.get_timesheet_detail(found[0]["name"])

    day_logs = [log for log in detail.get("time_logs") or [] if str(log.get("from_time") or "").startswith(iso)]
    hours = round(sum(float(log.get("hours") or 0) for log in day_logs), 2)

    if opts.json_mode:
        print(json.dumps({"date": iso, "hours_on_date": hours, "timesheet": detail},
                         indent=2, ensure_ascii=False, default=str))
        return
    _print_timesheet(detail, opts, None if no_logs else day_logs, extra=[(f"Logged on {iso}", f"{hours} h")])
