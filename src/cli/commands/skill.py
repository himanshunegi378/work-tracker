"""`samta-tracker install-skill`: teach an AI agent (Claude Code) to use this CLI."""

import json
from importlib import resources
from pathlib import Path
from typing import Optional

import typer

from src.cli.errors import ERROR, CliError, handle_errors
from src.cli.output import GlobalOptions, success

SKILL_NAME = "samta-tracker"


def skill_text() -> str:
    return resources.files("src.cli.skill").joinpath("SKILL.md").read_text(encoding="utf-8")


def target_dir(project: bool, directory: Optional[Path]) -> Path:
    if directory is not None:
        return directory.expanduser() / SKILL_NAME
    base = Path.cwd() / ".claude" / "skills" if project else Path.home() / ".claude" / "skills"
    return base / SKILL_NAME


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
    text = skill_text()
    if print_only:
        print(text)
        return

    dest = target_dir(project, directory) / "SKILL.md"
    status = "installed"
    if dest.exists():
        if dest.read_text(encoding="utf-8") == text:
            status = "up-to-date"
        elif not (force or opts.yes):
            raise CliError(f"{dest} already exists and differs.", ERROR,
                           hint="Overwrite it with: samta-tracker install-skill --force")
        else:
            status = "updated"
    if status != "up-to-date":
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise CliError(f"Could not write {dest}: {exc}", ERROR)

    if opts.json_mode:
        print(json.dumps({"status": status, "path": str(dest)}))
    elif status == "up-to-date":
        success(f"Skill already up to date at {dest}.", opts)
    else:
        success(f"Skill {status} at {dest}. Restart your agent to pick it up.", opts)
