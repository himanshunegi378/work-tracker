"""`samta-tracker setup`: one-time setup after unpacking the app (command on PATH + agent skill)."""

import json
import sys

import typer

from src.cli.errors import ERROR, CliError, handle_errors
from src.cli.output import GlobalOptions, success
from src.core import cli_setup


@handle_errors
def setup(
    ctx: typer.Context,
    skill: bool = typer.Option(True, "--skill/--no-skill", help="Also install the agent skill for Claude Code."),
    undo: bool = typer.Option(False, "--undo", help="Remove the command from your PATH again."),
) -> None:
    """Make `samta-tracker` work from any terminal, and install the agent skill.

    Run it once, by its full path, after unpacking the app. Safe to repeat.
    """
    opts: GlobalOptions = ctx.obj
    try:
        if undo:
            out = cli_setup.uninstall_command()
            result = {"command": out.message}
            note = None
        else:
            out = cli_setup.install_command()
            result = {"command": out.message}
            note = out.hint
            if skill:
                status, dest = cli_setup.install_skill(force=True)
                result["skill"] = f"{status}: {dest}"
    except cli_setup.SetupError as exc:
        raise CliError(str(exc), ERROR)

    if opts.json_mode:
        print(json.dumps({**result, "restart_terminal": out.restart_terminal}))
        return
    for line in result.values():
        success(line, opts)
    if note:
        print(note, file=sys.stderr)
    elif out.restart_terminal and not undo:
        success("Open a new terminal, then try: samta-tracker status", opts)
