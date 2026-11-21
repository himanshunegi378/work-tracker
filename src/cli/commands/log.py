"""`samta-tracker log add | list`: record and view time against projects."""

import json
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import typer

from src.cli.commands._common import (
    ALL_OPTION, LIMIT_OPTION, PAGE_OPTION, day_total_hours, load_timesheet_for_day, logs_on_day,
)
from src.cli.commands.timesheets import _LOG_COLUMNS, _log_rows
from src.cli.context import get_context
from src.cli.errors import ERROR, USAGE, CliError, handle_errors
from src.cli.output import GlobalOptions, emit_data, render_details, success
from src.core import dates, ipc, prefs
from src.core.durations import format_duration, parse_duration
from src.core.log_plan import LogPlan, PlanError, plan_log

log_app = typer.Typer(help="Record time against projects and view your entries.", no_args_is_help=True)


def _interactive() -> bool:
    return sys.stdin.isatty()


def _need(value: Optional[str], label: str, flag: str, default: Optional[str] = None) -> str:
    """Return `value`, prompting for it in a terminal, or fail with a usage error."""
    if value and value.strip():
        return value.strip()
    if not _interactive():
        raise CliError(f"{label} is required. Pass {flag}.", USAGE)
    answer = typer.prompt(label, default=default or "", show_default=bool(default)).strip()
    if not answer:
        raise CliError(f"{label} is required.", USAGE)
    return answer


def _resolve_project(service, text: str) -> Tuple[str, str]:
    """Match `text` to one project (id or name). Returns (id, name)."""
    wanted = text.strip().lower()
    found = service.get_projects(search_text=text.strip(), page_length=50)
    exact = [p for p in found if wanted in (str(p.get("id", "")).lower(), str(p.get("name", "")).lower())]
    matches = exact or found
    if len(matches) == 1:
        return str(matches[0]["id"]), str(matches[0]["name"])
    if not matches:
        raise CliError(f"No project matches '{text}'.", USAGE, hint="See `samta-tracker projects list`.")
    options = ", ".join(f"{p['id']} ({p['name']})" for p in matches[:8])
    raise CliError(f"'{text}' matches several projects: {options}", USAGE, hint="Pass the exact project id with -p.")


def _resolve_activity(service, text: str) -> str:
    wanted = text.strip().lower()
    names = service.get_activity_names(search_text=text.strip(), page_length=200)
    exact = [n for n in names if n.lower() == wanted]
    matches = exact or names
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CliError(f"No activity matches '{text}'.", USAGE, hint="See `samta-tracker activities list`.")
    raise CliError(
        f"'{text}' matches several activities: {', '.join(matches[:8])}", USAGE,
        hint="Pass the exact activity name with -a.",
    )


def _pick_recent(timesheets) -> Dict[str, Any]:
    if not _interactive():
        raise CliError("--recent needs an interactive terminal.", USAGE)
    options = timesheets.get_recent_smart_log_options(limit=5)
    if not options:
        raise CliError("No recent entries to choose from.", ERROR)
    for number, option in enumerate(options, 1):
        print(f"  {number}) {option['project_id']} · {option['project_name']} · {option['activity_name']}", file=sys.stderr)
    while True:
        choice = typer.prompt("Pick one", type=int, default=1)
        if 1 <= choice <= len(options):
            return options[choice - 1]
        print(f"Enter a number from 1 to {len(options)}.", file=sys.stderr)


def _parse_when(date_text: Optional[str], at_text: Optional[str], duration: Optional[int], today: date) -> Optional[datetime]:
    """Turn --date/--at into the entry's end time, or None to mean 'now'."""
    try:
        day = dates.parse_date(date_text) if date_text else None
        at = dates.parse_time(at_text) if at_text else None
    except ValueError as exc:
        raise CliError(str(exc), USAGE)
    if day and day > today:
        raise CliError("--date is in the future.", USAGE)
    if day and day != today and at is None:
        raise CliError("--date for a past day also needs --at (the end time) and --duration.", USAGE)
    if at is None:
        return None
    if duration is None:
        raise CliError("--at needs --duration (the entry's length).", USAGE)
    return datetime.combine(day or today, at)


def _preview(plan: LogPlan, project: Tuple[str, str], activity: str, description: str, billable: bool, opts: GlobalOptions) -> str:
    where = plan.timesheet_name or f"timesheet for {plan.to_dt:%Y-%m-%d} (created if missing)"
    pairs = [
        ("Project", f"{project[0]} · {project[1]}"),
        ("Activity", activity),
        ("Description", description),
        ("Billable", billable),
        ("When", f"{plan.from_dt:%Y-%m-%d %H:%M} → {plan.to_dt:%H:%M}  ({plan.duration_text})"),
        ("Saves as", "extends your previous entry" if plan.merges else "a new entry"),
        ("Timesheet", where),
    ]
    block = render_details(pairs, opts.color)
    return block + "".join(f"\n! {note}" for note in plan.notes)


def _notify_desktop_app() -> None:
    """If the desktop app is open, ask it to refresh. Never fails the command."""
    try:
        ipc.request("data.refresh", timeout=1.0)
    except (ipc.IpcUnavailable, ipc.IpcError):
        pass


@log_app.command("add")
@handle_errors
def add(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, "-p", "--project", help="Project id or name."),
    activity: Optional[str] = typer.Option(None, "-a", "--activity", help="Activity type."),
    description: Optional[str] = typer.Option(None, "-d", "--description", help="What you did."),
    duration: Optional[str] = typer.Option(None, "--duration", help="Length, e.g. 45m or 1h30m (default: since your previous entry)."),
    billable: Optional[bool] = typer.Option(None, "--billable/--no-billable", help="Billable? (default: as your last entry)."),
    date_: Optional[str] = typer.Option(None, "--date", help=f"Day to log against ({dates.HELP}). Past days also need --at and --duration."),
    at: Optional[str] = typer.Option(None, "--at", help=f"When the entry ends ({dates.TIME_HELP}). Needs --duration."),
    recent: bool = typer.Option(False, "--recent", help="Pick a recent project and activity from a list."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be saved, without saving."),
) -> None:
    """Record time on a project (the same logic as the desktop Smart Log)."""
    opts: GlobalOptions = ctx.obj
    app = get_context(ctx)
    today = date.today()

    try:
        duration_seconds = parse_duration(duration) if duration is not None else None
    except ValueError as exc:
        raise CliError(f"--duration: {exc}", USAGE)
    end_at = _parse_when(date_, at, duration_seconds, today)

    picked: Dict[str, Any] = _pick_recent(app.timesheets) if recent else {}
    previous = app.timesheets.get_latest_smart_log_state()

    # project / activity / description
    if project or not picked:
        project_id, project_name = _resolve_project(app.projects, _need(project, "Project", "-p"))
    else:
        project_id, project_name = picked["project_id"], picked["project_name"]
    if activity or not picked:
        activity_name = _resolve_activity(app.activities, _need(activity, "Activity", "-a"))
    else:
        activity_name = picked["activity_name"]
    text = _need(description, "Description", "-d", default=picked.get("description"))

    if billable is None:
        same_as_last = previous and previous.get("project_id") == project_id and previous.get("activity_name") == activity_name
        default = picked.get("is_billable", bool(same_as_last and previous.get("is_billable")))
        billable = typer.confirm("Billable?", default=default) if _interactive() and not opts.yes else default

    try:
        plan = plan_log(
            previous_state=previous, project_id=project_id, activity=activity_name, description=text,
            is_billable=billable, now=datetime.now(), duration_seconds=duration_seconds,
            default_interval_seconds=prefs.get_interval_seconds(), end_at=end_at,
        )
    except PlanError as exc:
        raise CliError(str(exc), USAGE)

    summary = {
        "project_id": project_id, "project_name": project_name, "activity": activity_name, "description": text,
        "billable": billable, "from": plan.from_dt.isoformat(sep=" "), "to": plan.to_dt.isoformat(sep=" "),
        "hours": round(plan.hours, 4), "extends_previous": plan.merges, "timesheet": plan.timesheet_name,
        "notes": plan.notes,
    }

    if dry_run:
        if opts.json_mode:
            print(json.dumps({"dry_run": True, **summary}, indent=2, ensure_ascii=False))
        else:
            print(_preview(plan, (project_id, project_name), activity_name, text, billable, opts))
            success("Dry run: nothing was saved.", opts)
        return

    if _interactive() and not opts.yes and not opts.json_mode:
        print(_preview(plan, (project_id, project_name), activity_name, text, billable, opts), file=sys.stderr)
        if not typer.confirm("Save this entry?", default=True):
            raise CliError("Nothing saved.", ERROR)

    detail = app.timesheets.save_timesheet_log(
        project_id=project_id, project_name=project_name, activity=activity_name, description=text,
        is_billable=billable, interval_seconds=plan.interval_seconds, saved_at=plan.saved_at,
    )
    day = f"{plan.to_dt:%Y-%m-%d}"
    day_hours = day_total_hours(detail, day)
    _notify_desktop_app()

    if opts.json_mode:
        print(json.dumps({"saved": True, **summary, "timesheet": detail.get("name"), "hours_on_date": round(day_hours, 4)},
                         indent=2, ensure_ascii=False))
        return
    verb = "Extended entry by" if plan.merges else "Logged"
    when = "today" if plan.to_dt.date() == today else day
    success(
        f"{verb} {plan.duration_text} on {project_id} / {activity_name} in {detail.get('name')} "
        f"(total {when}: {format_duration(round(day_hours * 3600 / 60) * 60 if day_hours >= 1 / 60 else round(day_hours * 3600))})",
        opts,
    )


@log_app.command("list")
@handle_errors
def list_(
    ctx: typer.Context,
    on: Optional[str] = typer.Option(None, "--date", help=f"Day to show, default today ({dates.HELP})."),
    timesheet: Optional[str] = typer.Option(None, "--timesheet", help="Show all entries of this timesheet instead."),
) -> None:
    """List your time entries for a day (default today) or for a whole timesheet."""
    opts: GlobalOptions = ctx.obj
    if on and timesheet:
        raise CliError("Use either --date or --timesheet, not both.", USAGE)
    service = get_context(ctx).timesheets

    if timesheet:
        detail = service.get_timesheet_detail(timesheet.strip())
        logs, label = detail.get("time_logs") or [], timesheet.strip()
    else:
        try:
            day = dates.parse_date(on) if on else date.today()
        except ValueError as exc:
            raise CliError(f"--date: {exc}", USAGE)
        iso = day.isoformat()
        try:
            detail = load_timesheet_for_day(service, iso)
        except CliError:
            detail = {"time_logs": []}
        logs, label = logs_on_day(detail, iso), iso

    rows = logs if opts.json_mode else _log_rows(logs)  # JSON keeps the raw server values
    total = day_total_hours(detail, iso) if not timesheet else float(detail.get("total_hours") or 0)
    if not rows and not opts.json_mode:
        if not opts.quiet:
            print(f"No entries for {label}.", file=sys.stderr)
        return
    footer = f"{len(rows)} {'entry' if len(rows) == 1 else 'entries'} · {format_duration(round(total * 3600))} total"
    emit_data(rows, _LOG_COLUMNS, opts, footer=footer, quiet_key="name")
