"""`samta-tracker projects list | view`."""

import json
from enum import Enum
from typing import Optional

import typer

from src.cli.commands._common import ALL_OPTION, LIMIT_OPTION, PAGE_OPTION, SEARCH_OPTION, run_list
from src.cli.context import get_context
from src.cli.errors import ERROR, CliError, handle_errors
from src.cli.output import GlobalOptions, render_details

projects_app = typer.Typer(help="List and inspect projects.", no_args_is_help=True)


class Status(str, Enum):
    open = "open"
    completed = "completed"
    cancelled = "cancelled"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


@projects_app.command("list")
@handle_errors
def list_(
    ctx: typer.Context,
    search: Optional[str] = SEARCH_OPTION,
    status: Optional[Status] = typer.Option(None, "--status", help="Only projects with this status."),
    priority: Optional[Priority] = typer.Option(None, "--priority", help="Only projects with this priority."),
    active: Optional[bool] = typer.Option(None, "--active/--inactive", help="Only active (or only inactive) projects."),
    limit: Optional[int] = LIMIT_OPTION,
    page: int = PAGE_OPTION,
    all_pages: bool = ALL_OPTION,
) -> None:
    """List projects."""
    service = get_context(ctx).projects
    filters = {}
    if status:
        filters["status"] = status.value.capitalize()
    if priority:
        filters["priority"] = priority.value.capitalize()

    def fetch(start: int, count: int):
        return service.get_projects(
            search_text=search or "", start=start, page_length=count, filters=json.dumps(filters)
        )

    def only_active(rows):
        return [r for r in rows if bool(r.get("is_active")) == active]

    run_list(
        ctx, fetch,
        [("id", "ID"), ("name", "NAME"), ("status", "STATUS"), ("priority", "PRIORITY"), ("is_active", "ACTIVE")],
        noun="projects", quiet_key="id", limit=limit, page=page, all_pages=all_pages,
        post_filter=only_active if active is not None else None,
    )


@projects_app.command("view")
@handle_errors
def view(ctx: typer.Context, project_id: str = typer.Argument(..., metavar="ID", help="Project id, e.g. PROJ-0012.")) -> None:
    """Show one project's details."""
    opts: GlobalOptions = ctx.obj
    wanted = project_id.strip().lower()
    matches = [
        p for p in get_context(ctx).projects.get_projects(search_text=project_id.strip(), page_length=20)
        if wanted in (str(p.get("id", "")).lower(), str(p.get("name", "")).lower())
    ]
    if not matches:
        raise CliError(f"Project '{project_id}' not found.", ERROR, hint="Try `samta-tracker projects list -s <text>`.")
    project = matches[0]

    if opts.json_mode:
        print(json.dumps(project, indent=2, ensure_ascii=False, default=str))
        return
    print(render_details(
        [
            ("ID", project.get("id")), ("Name", project.get("name")), ("Status", project.get("status")),
            ("Priority", project.get("priority")), ("Active", project.get("is_active")),
            ("Description", project.get("description")),
        ],
        opts.color,
    ))
