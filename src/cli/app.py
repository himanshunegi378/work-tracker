"""Root of the `samta-tracker` command line."""

from typing import Optional

import typer

from src.cli import __version__
from src.cli.output import GlobalOptions

app = typer.Typer(
    name="samta-tracker",
    help="Work Tracker from your terminal: the same app as the desktop GUI.",
    no_args_is_help=True,
    add_completion=True,
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
    _configure_cli_logging()


def _configure_cli_logging() -> None:
    """Send library logs to a file so they never pollute stdout/stderr."""
    try:
        from src.core.logging_setup import configure_logging
        from src.runtime_paths import user_log_dir

        configure_logging(user_log_dir() / "cli.log")
    except OSError:
        import logging

        logging.getLogger().addHandler(logging.NullHandler())  # still silence the last-resort handler


def _register_commands() -> None:
    from src.cli.commands import activities, auth, completion, config, employees, leave, log, projects, setup, skill, timesheets, tracker

    app.command("login")(auth.login)
    app.command("logout")(auth.logout)
    app.add_typer(auth.auth_app, name="auth")
    app.add_typer(config.config_app, name="config")
    app.add_typer(projects.projects_app, name="projects")
    app.add_typer(activities.activities_app, name="activities")
    app.add_typer(timesheets.timesheets_app, name="timesheets")
    app.command("employees")(employees.employees)
    app.add_typer(leave.leave_app, name="leave")
    app.add_typer(log.log_app, name="log")
    app.command("start")(tracker.start)
    app.command("stop")(tracker.stop)
    app.command("status")(tracker.status)
    app.command("gui")(tracker.gui)
    app.command("remind")(tracker.remind)
    app.command("completion")(completion.completion)
    app.command("install-skill")(skill.install_skill)
    app.command("setup")(setup.setup)


_register_commands()


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
