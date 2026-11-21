"""Root of the `samta-tracker` command line."""

from typing import Optional

import typer

from src.cli import __version__
from src.cli.output import GlobalOptions

app = typer.Typer(
    name="samta-tracker",
    help="Work Tracker from your terminal: the same app as the desktop GUI.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"samta-tracker {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Print only ids/names, one per line."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompts."),
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    ctx.obj = GlobalOptions(json_mode=json_mode, no_color=no_color, quiet=quiet, yes=yes)


def get_context(ctx: typer.Context):
    """Build the shared AppContext lazily so `--help` stays instant."""
    from src.core.app import build_app

    state = ctx.find_root().meta
    if "app_ctx" not in state:
        state["app_ctx"] = build_app()
    return state["app_ctx"]


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
