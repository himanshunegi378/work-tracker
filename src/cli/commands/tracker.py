"""`samta-tracker start | stop | status | gui | remind`: control the reminder tracker."""

import json
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

import typer

from src.cli import gui_launcher
from src.cli.commands.auth import _current_user, _host
from src.cli.context import get_context
from src.cli.errors import ERROR, USAGE, CliError, handle_errors, message_for
from src.cli.output import GlobalOptions, render_details, success
from src.core import ipc, prefs
from src.core.durations import format_duration, parse_duration

EVERY_HELP = "Reminder interval, e.g. 15m or 1h (1m to 24h). Default: the `interval` setting."


def _parse_every(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    try:
        seconds = parse_duration(text)
    except ValueError as exc:
        raise CliError(f"--every: {exc}", USAGE)
    if not prefs.MIN_INTERVAL_SECONDS <= seconds <= prefs.MAX_INTERVAL_SECONDS:
        raise CliError("--every must be between 1m and 24h.", USAGE)
    return seconds


def _ask(cmd: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send a command to the running app, turning protocol errors into CLI errors."""
    try:
        return ipc.request(cmd, args)
    except ipc.IpcUnavailable as exc:
        raise CliError(str(exc), ERROR, hint="Start it with `samta-tracker start` or `samta-tracker gui`.")
    except ipc.IpcError as exc:
        raise CliError(str(exc), ERROR)


def _tracker_line(tracker: Dict[str, Any]) -> str:
    if not tracker.get("active"):
        return "inactive"
    every = format_duration(tracker["interval_seconds"])
    nxt = tracker.get("next_prompt_in_seconds")
    when = f" · next prompt in {format_duration(max(nxt, 1))}" if nxt is not None else ""
    return f"active · every {every}{when}"


@handle_errors
def start(
    ctx: typer.Context,
    every: Optional[str] = typer.Option(None, "--every", help=EVERY_HELP),
    show: bool = typer.Option(False, "--show", help="Also open the window (default: start in the tray)."),
) -> None:
    """Start the reminder tracker in the desktop app (launching it if needed)."""
    opts: GlobalOptions = ctx.obj
    seconds = _parse_every(every)
    launched = gui_launcher.ensure_gui(hidden=not show)
    if launched and not opts.json_mode and not opts.quiet:
        print("Started the desktop app" + ("" if show else " in the tray") + ".", file=sys.stderr)
    elif show:
        _ask("window.show")

    status = _ask("tracker.start", {"every": seconds} if seconds else {})
    if opts.json_mode:
        print(json.dumps({"launched_app": launched, **status}, indent=2))
        return
    success(f"Tracker started · reminders every {format_duration(status['tracker']['interval_seconds'])}", opts)
    if not opts.quiet:
        print("A log prompt opens now, then repeats on that interval.", file=sys.stderr)


@handle_errors
def stop(
    ctx: typer.Context,
    quit_app: bool = typer.Option(False, "--quit", help="Also close the desktop app."),
) -> None:
    """Stop the reminder tracker (closing the app too if the CLI started it and nobody opened it)."""
    opts: GlobalOptions = ctx.obj
    if not ipc.is_running():
        if opts.json_mode:
            print(json.dumps({"running": False}))
        else:
            success("Nothing to stop: the desktop app isn't running.", opts)
        return

    status = _ask("tracker.stop")
    closed = quit_app or (status.get("started_hidden") and not status.get("window_shown"))
    if closed:
        _ask("app.quit")
        gui_launcher.wait_until_stopped()

    if opts.json_mode:
        print(json.dumps({"tracker_active": False, "app_closed": bool(closed)}))
    else:
        success("Tracker stopped" + (" · desktop app closed" if closed else ""), opts)


@handle_errors
def status(ctx: typer.Context) -> None:
    """Show your login, the desktop app, the tracker and the dashboard counts."""
    opts: GlobalOptions = ctx.obj
    app = get_context(ctx)
    server = _host(app.api_client.base_url)

    running = ipc.is_running()
    gui = _ask("tracker.status") if running else None
    user = _current_user(app.auth)
    projects = timesheets = None
    if user:  # same numbers as the dashboard in the desktop app
        projects = len(app.projects.get_project_names(page_length=200))
        timesheets = len(app.timesheets.get_timesheets(page_length=20))

    if opts.json_mode:
        print(json.dumps({
            "logged_in": bool(user), "user": user, "server": server,
            "app_running": running, "tracker": gui["tracker"] if gui else None,
            "window_visible": gui["window_visible"] if gui else None,
            "projects": projects, "timesheet_rows": timesheets,
        }, indent=2))
        return

    if gui:
        where = "window open" if gui["window_visible"] else ("tray" if gui["tray"] else "window minimized")
        desktop, tracker = f"running ({where})", _tracker_line(gui["tracker"])
    else:
        desktop, tracker = "not running", "inactive (start it with `samta-tracker start`)"
    print(render_details(
        [
            ("User", user or "not logged in (run `samta-tracker login`)"),
            ("Server", server),
            ("Desktop", desktop),
            ("Tracker", tracker),
            ("Projects", projects),
            ("Timesheet rows", f"{timesheets} (latest 20)" if timesheets is not None else None),
        ],
        opts.color,
    ))


@handle_errors
def gui(ctx: typer.Context) -> None:
    """Open the desktop app window (or bring it forward if it is already open)."""
    opts: GlobalOptions = ctx.obj
    launched = gui_launcher.ensure_gui(hidden=False)
    if not launched:
        _ask("window.show")
    if opts.json_mode:
        print(json.dumps({"launched_app": launched}))
    else:
        success("Opened the desktop app." if launched else "Brought the desktop app forward.", opts)


# ── remind: foreground reminders for sessions without a display ───────────
def run_reminders(
    interval_seconds: int,
    on_tick: Callable[[], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    max_ticks: Optional[int] = None,
    announce: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
) -> int:
    """Wait `interval_seconds`, call `on_tick`, repeat. Ctrl+C stops. Returns the tick count."""
    ticks = 0
    try:
        while max_ticks is None or ticks < max_ticks:
            due = clock() + interval_seconds
            announce(f"Next reminder at {datetime.fromtimestamp(due):%H:%M} (Ctrl+C to stop).")
            while clock() < due:
                sleep(min(1.0, max(0.0, due - clock())))
            ticks += 1
            on_tick()
    except KeyboardInterrupt:
        announce("\nStopped reminders.")
    return ticks


def _log_prompt(ctx: typer.Context) -> None:
    """One reminder: offer to log, using recent entries when there are any."""
    from src.cli.commands import log as log_cmd

    print("\a", end="", file=sys.stderr)  # terminal bell
    print("\n⏰ Time to log your work.", file=sys.stderr)
    if not typer.confirm("Log it now?", default=True):
        return
    add = log_cmd.add.__wrapped__  # the command body without the exit-code wrapper
    for use_recent in (True, False):
        try:
            add(ctx, project=None, activity=None, description=None, duration=None, billable=None,
                date_=None, at=None, recent=use_recent, dry_run=False)
            return
        except CliError as exc:
            if use_recent and "No recent entries" in exc.message:
                continue  # nothing to pick from: ask for the details instead
            print(f"✗ {exc.message}", file=sys.stderr)
            return
        except Exception as exc:  # noqa: BLE001 - keep reminding after a failed save
            print(f"✗ {message_for(exc)}", file=sys.stderr)
            return


@handle_errors
def remind(
    ctx: typer.Context,
    every: Optional[str] = typer.Option(None, "--every", help=EVERY_HELP),
) -> None:
    """Remind you to log time, here in the terminal (for sessions without a display)."""
    if not sys.stdin.isatty():
        raise CliError("`remind` needs an interactive terminal.", USAGE)
    seconds = _parse_every(every) or prefs.get_interval_seconds()
    get_context(ctx)  # fail fast if the app can't be wired up
    ticks = run_reminders(seconds, lambda: _log_prompt(ctx))
    if ticks:
        print(f"{ticks} reminder(s) shown.", file=sys.stderr)
