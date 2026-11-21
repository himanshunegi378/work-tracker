import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typer
from typer.testing import CliRunner

from src.api import AuthenticationRequiredError
from src.cli import errors
from src.cli.output import GlobalOptions, emit_data, render_table, style

COLUMNS = [("id", "ID"), ("name", "NAME"), ("active", "ACTIVE")]
ROWS = [
    {"id": "PROJ-1", "name": "Billing", "active": True},
    {"id": "PROJ-22", "name": None, "active": False},
]


def test_render_table_aligns_columns_and_fills_blanks():
    lines = render_table(ROWS, COLUMNS).split("\n")
    assert lines[0].split() == ["ID", "NAME", "ACTIVE"]
    assert lines[1].split() == ["PROJ-1", "Billing", "yes"]
    assert lines[2].split() == ["PROJ-22", "-", "no"]
    # every row has its NAME cell at the header's NAME offset (id column is 7 wide + 2 gap)
    offset = lines[0].index("NAME")
    assert offset == 9
    assert lines[1][offset:].startswith("Billing")
    assert lines[2][offset:].startswith("-")


def test_render_table_empty_rows_still_prints_header():
    assert render_table([], COLUMNS).strip().split() == ["ID", "NAME", "ACTIVE"]


def test_emit_json_is_valid(capsys):
    emit_data(ROWS, COLUMNS, GlobalOptions(json_mode=True))
    assert json.loads(capsys.readouterr().out) == ROWS


def test_emit_quiet_prints_only_ids(capsys):
    emit_data(ROWS, COLUMNS, GlobalOptions(quiet=True), quiet_key="id")
    assert capsys.readouterr().out.split() == ["PROJ-1", "PROJ-22"]


def test_color_off_for_no_color_flag_and_env(monkeypatch):
    assert GlobalOptions(no_color=True).color is False
    monkeypatch.setenv("NO_COLOR", "1")
    assert GlobalOptions().color is False
    assert style("x", "red", color=False) == "x"
    assert "\x1b[" in style("x", "red", color=True)


def _app_raising(exc):
    sub = typer.Typer()

    @sub.command()
    @errors.handle_errors
    def boom():
        raise exc

    @sub.command()
    def other():  # second command so Typer keeps `boom` as a named subcommand
        pass

    return sub


def test_auth_error_maps_to_exit_3():
    result = CliRunner().invoke(_app_raising(AuthenticationRequiredError("no session")), ["boom"])
    assert result.exit_code == errors.NOT_LOGGED_IN
    assert "samta-tracker login" in result.output


def test_generic_error_maps_to_exit_1():
    result = CliRunner().invoke(_app_raising(RuntimeError("kaboom")), ["boom"])
    assert result.exit_code == errors.ERROR
    assert "kaboom" in result.output


def test_cli_error_keeps_its_exit_code_and_hint():
    exc = errors.CliError("no display", errors.GUI_UNAVAILABLE, hint="use remind")
    result = CliRunner().invoke(_app_raising(exc), ["boom"])
    assert result.exit_code == errors.GUI_UNAVAILABLE
    assert "no display" in result.output and "use remind" in result.output


def test_exit_code_constants_match_spec():
    assert (errors.OK, errors.ERROR, errors.USAGE, errors.NOT_LOGGED_IN, errors.GUI_UNAVAILABLE) == (0, 1, 2, 3, 4)
