"""`samta-tracker completion SHELL`: print or install tab-completion for a shell."""

import json
from enum import Enum

import typer

from src.cli.errors import ERROR, CliError, handle_errors
from src.cli.output import GlobalOptions, success

PROG_NAME = "samta-tracker"
COMPLETE_VAR = "_SAMTA_TRACKER_COMPLETE"


class Shell(str, Enum):
    bash = "bash"
    zsh = "zsh"
    fish = "fish"
    powershell = "powershell"


@handle_errors
def completion(
    ctx: typer.Context,
    shell: Shell = typer.Argument(..., help="Shell to generate completion for."),
    install: bool = typer.Option(False, "--install", help="Install it for your user instead of printing it."),
) -> None:
    """Print the tab-completion script for a shell (or install it with --install).

    Try: eval "$(samta-tracker completion bash)"   or   samta-tracker completion zsh --install
    """
    from typer._completion_shared import get_completion_script
    from typer._completion_shared import install as install_script

    opts: GlobalOptions = ctx.obj
    if not install:
        print(get_completion_script(prog_name=PROG_NAME, complete_var=COMPLETE_VAR, shell=shell.value))
        return
    try:
        _, path = install_script(shell=shell.value, prog_name=PROG_NAME, complete_var=COMPLETE_VAR)
    except Exception as exc:  # noqa: BLE001 - shells differ a lot; report plainly
        raise CliError(f"Could not install completion for {shell.value}: {exc}", ERROR,
                       hint=f"Print it instead: samta-tracker completion {shell.value}")
    if opts.json_mode:
        print(json.dumps({"installed": True, "shell": shell.value, "path": str(path)}))
    else:
        success(f"Completion installed for {shell.value} in {path}. Restart your shell to use it.", opts)
