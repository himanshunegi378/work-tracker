"""`samta-tracker leave list | balance`."""

from datetime import date
from enum import Enum
from typing import Optional

import typer

from src.cli.commands._common import ALL_OPTION, LIMIT_OPTION, PAGE_OPTION, run_list
from src.cli.context import get_context
from src.cli.errors import USAGE, CliError, handle_errors
from src.cli.output import emit_data
from src.core import dates

leave_app = typer.Typer(help="List your leave applications and balances.", no_args_is_help=True)


class Status(str, Enum):
    open = "open"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


def _parse(value: Optional[str], flag: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return dates.parse_date(value)
    except ValueError as exc:
        raise CliError(f"{flag}: {exc}", USAGE)


@leave_app.command("list")
@handle_errors
def list_(
    ctx: typer.Context,
    status: Optional[Status] = typer.Option(None, "--status", help="Only leaves with this status."),
    leave_type: Optional[str] = typer.Option(None, "--type", help="Exact leave type, e.g. 'Sick Leave'."),
    from_: Optional[str] = typer.Option(None, "--from", help=f"Ending on or after this date ({dates.HELP})."),
    to: Optional[str] = typer.Option(None, "--to", help=f"Starting on or before this date ({dates.HELP})."),
    employee: Optional[str] = typer.Option(None, "--employee", help="Employee id (default: you)."),
    limit: Optional[int] = LIMIT_OPTION,
    page: int = PAGE_OPTION,
    all_pages: bool = ALL_OPTION,
) -> None:
    """List your leave applications, newest first."""
    from_date, to_date = _parse(from_, "--from"), _parse(to, "--to")
    if from_date and to_date and from_date > to_date:
        raise CliError("--from is after --to.", USAGE)
    service = get_context(ctx).leave

    def fetch(start: int, count: int):
        return service.get_leave_applications(
            start=start, page_length=count, employee=employee,
            status=status.value.capitalize() if status else None, leave_type=leave_type,
            from_date=from_date, to_date=to_date,
        )

    run_list(
        ctx, fetch,
        [("name", "ID"), ("employee_name", "EMPLOYEE"), ("leave_type", "TYPE"), ("from_date", "FROM"), ("to_date", "TO"),
         ("total_leave_days", "DAYS"), ("status", "STATUS")],
        noun="leave applications", quiet_key="name", limit=limit, page=page, all_pages=all_pages,
    )


@leave_app.command("balance")
@handle_errors
def balance(
    ctx: typer.Context,
    on: Optional[str] = typer.Option(None, "--date", help=f"Balance as of this date ({dates.HELP}); default today."),
    employee: Optional[str] = typer.Option(None, "--employee", help="Employee id (default: you)."),
) -> None:
    """Show leaves allocated, taken and remaining for each leave type."""
    on_date = _parse(on, "--date")
    rows = get_context(ctx).leave.get_leave_balance(employee=employee, on_date=on_date)
    emit_data(
        rows,
        [("leave_type", "TYPE"), ("total_leaves", "ALLOCATED"), ("leaves_taken", "TAKEN"),
         ("leaves_pending_approval", "PENDING"), ("remaining_leaves", "REMAINING")],
        ctx.obj, quiet_key="leave_type",
    )
