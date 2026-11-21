"""`samta-tracker config get|set` (shared with the desktop app)."""

import json
from typing import Optional

import typer

from src.cli.errors import USAGE, CliError, handle_errors
from src.cli.output import GlobalOptions, emit_data, success
from src.core import prefs

def _complete_key(incomplete: str):
    return [k for k in prefs.keys() if k.startswith(incomplete)]


def _complete_value(ctx: typer.Context, incomplete: str):
    key = ctx.params.get("key")
    if key == "theme":
        return [t for t in prefs.THEMES if t.startswith(incomplete)]
    return []


config_app = typer.Typer(help="Read and change settings shared with the desktop app.", no_args_is_help=True)

_NOTES = {
    "theme": "The desktop app picks this up the next time it opens.",
    "url": "Takes effect on the next command; log in again if you switch servers.",
    "interval": "Reminder interval, e.g. 15m or 1h30m (1m to 24h).",
}


@config_app.command("get")
@handle_errors
def get(
    ctx: typer.Context,
    key: Optional[str] = typer.Argument(None, help=f"One of: {', '.join(prefs.keys())}. Omit to list all.",
                                        autocompletion=_complete_key),
) -> None:
    """Show one setting, or all of them."""
    opts: GlobalOptions = ctx.obj
    try:
        if key:
            value = prefs.get(key)
            print(json.dumps({"key": key, "value": value}) if opts.json_mode else value)
            return
        rows = [{"key": k, "value": v} for k, v in prefs.get_all().items()]
    except prefs.PrefError as exc:
        raise CliError(str(exc), USAGE)
    if opts.json_mode:
        print(json.dumps(prefs.get_all(), indent=2))
    else:
        emit_data(rows, [("key", "KEY"), ("value", "VALUE")], opts, quiet_key="key")


@config_app.command("set")
@handle_errors
def set_(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=f"One of: {', '.join(prefs.keys())}", autocompletion=_complete_key),
    value: str = typer.Argument(..., help="New value.", autocompletion=_complete_value),
) -> None:
    """Change a setting."""
    opts: GlobalOptions = ctx.obj
    try:
        saved = prefs.set_value(key, value)
    except prefs.PrefError as exc:
        raise CliError(str(exc), USAGE)
    if opts.json_mode:
        print(json.dumps({"key": key, "value": saved}))
    else:
        success(f"{key} = {saved}   ({_NOTES[key]})", opts)
