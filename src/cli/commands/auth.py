"""`samta-tracker login | logout | auth status`."""

import json
import sys
from typing import Optional
from urllib.parse import urlparse

import typer

from src.cli.context import get_context
from src.cli.errors import ERROR, NOT_LOGGED_IN, USAGE, CliError, handle_errors
from src.cli.output import GlobalOptions, success
from src.core import prefs

auth_app = typer.Typer(help="Log in, log out and check your session.", no_args_is_help=True)

_GUEST = (None, "", "Guest")


def _host(url: str) -> str:
    return urlparse(url).netloc or url


def _prompt(label: str, *, hide: bool, default: Optional[str] = None) -> str:
    if not sys.stdin.isatty():
        raise CliError(
            f"{label} is required and this is not an interactive terminal.",
            USAGE,
            hint="Pass --username, and --password-stdin to read the password from stdin.",
        )
    return typer.prompt(label, hide_input=hide, default=default, show_default=bool(default) and not hide)


def _current_user(auth) -> Optional[str]:
    """Return the logged-in user, auto-logging in with saved credentials if needed."""
    user = auth.getSession()
    if user in _GUEST:
        username, password = auth.get_saved_username(), auth.get_saved_password()
        if username and password and auth.login(username, password):
            user = auth.getSession()
    return None if user in _GUEST else user


@handle_errors
def login(
    ctx: typer.Context,
    username: Optional[str] = typer.Option(None, "-u", "--username", help="Username or email."),
    password_stdin: bool = typer.Option(False, "--password-stdin", help="Read the password from stdin."),
    url: Optional[str] = typer.Option(None, "--url", help="Server URL (saved for next time)."),
    ui: bool = typer.Option(False, "--ui", help="Enter the credentials in a window instead of the terminal."),
) -> None:
    """Log in and remember the credentials (shared with the desktop app)."""
    opts: GlobalOptions = ctx.obj
    if ui and password_stdin:
        raise CliError("--ui and --password-stdin can't be used together.", USAGE)
    try:
        new_url = prefs.validate_url(url) if url else None
    except prefs.PrefError as exc:
        raise CliError(str(exc), USAGE)

    app = get_context(ctx, new_url)
    server = _host(app.api_client.base_url)

    if ui:
        from src.cli.ui_login import prompt_login_ui

        user = prompt_login_ui(app.auth.login, server=server, username=username or app.auth.get_saved_username() or "")
        if not user:
            raise CliError("Login cancelled.", ERROR)
        if new_url:
            prefs.set_value("url", new_url)
        if opts.json_mode:
            print(json.dumps({"logged_in": True, "user": user, "server": server}))
        else:
            success(f"Logged in to {server} as {user}", opts)
        return

    if password_stdin and not username:
        raise CliError("--password-stdin needs --username (stdin carries only the password).", USAGE)
    if not username:
        username = _prompt("Username or email", hide=False, default=app.auth.get_saved_username())
    password = sys.stdin.readline().rstrip("\r\n") if password_stdin else _prompt("Password", hide=True)
    if not password:
        raise CliError("Password is empty.", USAGE)

    if not app.auth.login(username, password):
        raise CliError("Login failed. Check your username and password.", ERROR)
    if new_url:
        prefs.set_value("url", new_url)

    if opts.json_mode:
        print(json.dumps({"logged_in": True, "user": username, "server": server}))
    else:
        success(f"Logged in to {server} as {username}", opts)


@handle_errors
def logout(ctx: typer.Context) -> None:
    """Remove the saved credentials (same as 'Clear Credentials' in the desktop app)."""
    opts: GlobalOptions = ctx.obj
    get_context(ctx).auth.clear_saved_credentials()
    if opts.json_mode:
        print(json.dumps({"logged_in": False}))
    else:
        success("Logged out. Saved credentials removed.", opts)


@auth_app.command("status")
@handle_errors
def status(ctx: typer.Context) -> None:
    """Show the server, the logged-in user and whether credentials are saved."""
    opts: GlobalOptions = ctx.obj
    app = get_context(ctx)
    server = _host(app.api_client.base_url)
    saved = bool(app.auth.get_saved_username())
    user = _current_user(app.auth)

    if opts.json_mode:
        print(json.dumps({"logged_in": bool(user), "user": user, "server": server, "credentials_saved": saved}))
    elif user:
        success(f"{server} · {user} · session valid · credentials {'saved' if saved else 'not saved'}", opts)
    if not user:
        raise CliError("Not logged in. Run `samta-tracker login`.", NOT_LOGGED_IN)
