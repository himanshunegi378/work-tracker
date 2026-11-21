"""Keeps the desktop app and the CLI in step.

If you add a screen to the GUI, this fails until you say which CLI command(s)
cover it. If you add a CLI command, it fails until it is mapped or listed as
CLI-only and documented in docs/cli-spec.md.
"""

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest
import typer.main
from typer.testing import CliRunner

from src.cli.app import app
from src.core import prefs
from src.ui.views.sidebar_view import NAV_ITEMS

# GUI sidebar module id -> CLI commands that cover it
GUI_MODULES = {
    "home": ["status", "start", "stop"],            # dashboard counts + tracker toggle
    "projects": ["projects list", "projects view"],
    "activities": ["activities list"],
    "timesheets": ["timesheets list", "timesheets view", "timesheets today"],
    "settings": ["login", "logout", "auth status", "config get", "config set"],
}

# GUI features that are not sidebar modules -> CLI commands
OTHER_GUI_FEATURES = {
    "smart log dialog (tracker prompt)": ["log add", "log list"],
    "tray: open window": ["gui"],
    "tray: start/stop tracker": ["start", "stop"],
    "settings: theme": ["config set"],
    "settings: install command-line tool": ["setup"],
    # Timesheet Detail screen: row Edit/Delete buttons and Submit/Delete timesheet buttons
    "timesheet detail: edit entry": ["log edit"],
    "timesheet detail: delete entry": ["log rm"],
    "timesheet detail: submit timesheet": ["timesheets submit"],
    "timesheet detail: delete timesheet": ["timesheets rm"],
}

# CLI commands with no GUI screen of their own (deliberate)
CLI_ONLY = {"remind", "completion", "install-skill"}


def cli_commands():
    """All leaf command paths, e.g. 'projects list'."""
    found = set()

    def walk(group, prefix):
        for name, cmd in group.commands.items():
            if hasattr(cmd, "commands"):
                walk(cmd, prefix + [name])
            else:
                found.add(" ".join(prefix + [name]))

    walk(typer.main.get_command(app), [])
    return found


CLI = cli_commands()
MAPPED = {c for cmds in {**GUI_MODULES, **OTHER_GUI_FEATURES}.values() for c in cmds}


def test_every_gui_sidebar_module_has_a_cli_mapping():
    gui_ids = {module_id for _icon, _label, module_id in NAV_ITEMS}
    missing = gui_ids - set(GUI_MODULES)
    assert not missing, f"GUI modules without a declared CLI equivalent: {sorted(missing)}"
    stale = set(GUI_MODULES) - gui_ids
    assert not stale, f"Mapped GUI modules that no longer exist: {sorted(stale)}"


def test_every_mapped_command_exists_in_the_cli():
    missing = MAPPED - CLI
    assert not missing, f"Mapped CLI commands that do not exist: {sorted(missing)}"


def test_every_cli_command_is_mapped_or_declared_cli_only():
    unexplained = CLI - MAPPED - CLI_ONLY
    assert not unexplained, f"CLI commands with no GUI counterpart declared: {sorted(unexplained)}"
    assert CLI_ONLY <= CLI, f"CLI_ONLY lists commands that do not exist: {sorted(CLI_ONLY - CLI)}"


def test_every_cli_command_is_documented_in_the_spec():
    spec = (ROOT / "docs" / "cli-spec.md").read_text(encoding="utf-8")
    undocumented = [c for c in sorted(CLI) if f"samta-tracker {c}" not in spec]
    assert not undocumented, f"Commands missing from docs/cli-spec.md: {undocumented}"


@pytest.mark.parametrize("command", sorted(CLI))
def test_every_cli_command_has_working_help(command):
    result = CliRunner().invoke(app, [*command.split(), "--help"])
    assert result.exit_code == 0 and "Usage" in result.output


def test_the_detail_screen_really_has_the_buttons_the_mapping_claims():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from src.ui.views.timesheet_detail_view import TimesheetDetailView

    view = TimesheetDetailView()
    for attribute in ("edit_btn", "delete_entry_btn", "submit_btn", "delete_timesheet_btn"):
        assert hasattr(view, attribute), f"GUI action missing: {attribute}"


def test_the_settings_screen_really_has_the_setup_buttons():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from src.ui.views.settings_view import SettingsView

    view = SettingsView()
    for attribute in ("install_cli_btn", "copy_btn"):
        assert hasattr(view, attribute), f"GUI action missing: {attribute}"


def test_the_gui_settings_theme_choices_are_settable_from_the_cli(monkeypatch, tmp_path):
    # the GUI offers exactly these themes; `config set theme` must accept each
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")
    from src.ui.design import THEMES

    assert set(THEMES) == set(prefs.THEMES)
    for theme in THEMES:
        assert prefs.set_value("theme", theme) == theme


def test_dashboard_numbers_are_available_from_status_json():
    # the GUI dashboard shows project count, timesheet rows and tracker state
    source = (ROOT / "src" / "cli" / "commands" / "tracker.py").read_text(encoding="utf-8")
    for key in ('"projects"', '"timesheet_rows"', '"tracker"'):
        assert key in source


def test_cli_config_keys_cover_everything_the_gui_can_change():
    gui_writable = {"theme"}  # Settings screen: theme buttons (credentials go through login/logout)
    assert gui_writable <= set(prefs.keys())


def test_shell_completion_script_names_the_command():
    result = CliRunner().invoke(app, ["completion", "bash"])
    assert result.exit_code == 0 and "_SAMTA_TRACKER_COMPLETE" in result.output
    for shell in ("zsh", "fish", "powershell"):
        assert CliRunner().invoke(app, ["completion", shell]).exit_code == 0
    assert CliRunner().invoke(app, ["completion", "tcsh"]).exit_code == 2


def test_completion_install_writes_only_under_the_users_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    result = CliRunner().invoke(app, ["--json", "completion", "bash", "--install"])
    assert result.exit_code == 0, result.output
    assert str(tmp_path) in result.output
