import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typer.testing import CliRunner

from src.cli import __version__
from src.cli.app import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"samta-tracker {__version__}" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # CI sets GITHUB_ACTIONS/FORCE_COLOR, which makes the help colored; compare the plain text.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for flag in ("--json", "--no-color", "--quiet", "--yes"):
        assert flag in plain


def test_short_help_flag():
    assert runner.invoke(app, ["-h"]).exit_code == 0


def test_unknown_command_is_usage_error():
    assert runner.invoke(app, ["nope"]).exit_code == 2


def test_global_flags_accepted_together():
    result = runner.invoke(app, ["--json", "--no-color", "-q", "-y", "--help"])
    assert result.exit_code == 0
