"""`samta-tracker employees`: who's leave and timesheets you may see."""

import sys

import typer

from src.cli.context import get_context
from src.cli.errors import handle_errors
from src.cli.output import emit_data


@handle_errors
def employees(ctx: typer.Context) -> None:
    """List the employees whose leave and timesheets you may see (use the ID with --employee)."""
    rows = get_context(ctx).employees.get_employees()
    if not rows and not ctx.obj.json_mode:
        print("No employees found.", file=sys.stderr)
        return
    emit_data(rows, [("employee", "ID"), ("employee_name", "NAME")], ctx.obj, quiet_key="employee")
