"""`samta-tracker install-skill`: teach an AI agent (Claude Code) to use this CLI."""

import json
from pathlib import Path
from typing import Optional

import typer

from src.cli.errors import ERROR, CliError, handle_errors
from src.cli.output import GlobalOptions, success
from src.core import cli_setup


def target_dir(project: bool, directory: Optional[Path]) -> Optional[Path]:
    if directory is not None:
        return directory
    return Path.cwd() / ".claude" / "skills" if project else None


@handle_errors
def install_skill(
    ctx: typer.Context,
    project: bool = typer.Option(False, "--project", help="Install into ./.claude/skills (this project only) instead of your user folder."),
    directory: Optional[Path] = typer.Option(None, "--dir", help="Skills folder of another agent; the skill goes in <dir>/samta-tracker/."),
    force: bool = typer.Option(False, "--force", help="Overwrite a different existing copy."),
    print_only: bool = typer.Option(False, "--print", help="Print the skill instead of installing it."),
) -> None:
    """Install the agent skill so Claude Code (or a compatible agent) can drive samta-tracker.

    Default: ~/.claude/skills/samta-tracker/SKILL.md. Re-run after upgrading the app to refresh it.
    """
    opts: GlobalOptions = ctx.obj
    if print_only:
        print(cli_setup.skill_text())
        return
    try:
        status, dest = cli_setup.install_skill(target_dir(project, directory), force=force or opts.yes)
    except cli_setup.SetupError as exc:
        hint = "Overwrite it with: samta-tracker install-skill --force" if "differs" in str(exc) else None
        raise CliError(str(exc), ERROR, hint=hint)
    if opts.json_mode:
        print(json.dumps({"status": status, "path": str(dest)}))
    elif status == "up-to-date":
        success(f"Skill already up to date at {dest}.", opts)
    else:
        success(f"Skill {status} at {dest}. Restart your agent to pick it up.", opts)
