"""`samta-tracker activities list`."""

from typing import Optional

import typer

from src.cli.commands._common import ALL_OPTION, LIMIT_OPTION, PAGE_OPTION, SEARCH_OPTION, run_list
from src.cli.context import get_context
from src.cli.errors import handle_errors

activities_app = typer.Typer(help="List activity types.", no_args_is_help=True)


@activities_app.command("list")
@handle_errors
def list_(
    ctx: typer.Context,
    search: Optional[str] = SEARCH_OPTION,
    limit: Optional[int] = LIMIT_OPTION,
    page: int = PAGE_OPTION,
    all_pages: bool = ALL_OPTION,
) -> None:
    """List activity types."""
    service = get_context(ctx).activities

    def fetch(start: int, count: int):
        return service.get_activities(search_text=search or "", start=start, page_length=count)

    run_list(ctx, fetch, [("name", "NAME")], noun="activities", quiet_key="name",
             limit=limit, page=page, all_pages=all_pages)
