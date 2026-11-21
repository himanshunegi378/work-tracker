import json
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.core import cli_setup

runner = CliRunner()


@pytest.fixture
def fake_install(tmp_path, monkeypatch):
    """A fake unpacked app: <tmp>/app/samta-tracker, with HOME in <tmp>/home."""
    home = tmp_path / "home"
    home.mkdir()
    exe = tmp_path / "app" / "samta-tracker"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(cli_setup, "cli_executable", lambda: exe)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("PATH", "/usr/bin")
    return home, exe


def test_install_links_the_command_and_warns_when_not_on_path(fake_install):
    home, exe = fake_install
    out = cli_setup.install_command()
    link = home / ".local/bin/samta-tracker"
    assert link.is_symlink() and link.resolve() == exe.resolve()
    assert out.changed and out.restart_terminal and ".local/bin" in out.hint
    assert cli_setup.is_installed()


def test_install_is_idempotent_and_no_warning_when_on_path(fake_install, monkeypatch):
    home, _ = fake_install
    monkeypatch.setenv("PATH", f"/usr/bin{os.pathsep}{home / '.local/bin'}")
    cli_setup.install_command()
    out = cli_setup.install_command()
    assert not out.changed and out.hint is None and not out.restart_terminal


def test_install_never_overwrites_a_real_file(fake_install):
    home, _ = fake_install
    real = home / ".local/bin/samta-tracker"
    real.parent.mkdir(parents=True)
    real.write_text("mine")
    with pytest.raises(cli_setup.SetupError):
        cli_setup.install_command()
    assert real.read_text() == "mine"


def test_uninstall_removes_only_the_link(fake_install):
    home, exe = fake_install
    cli_setup.install_command()
    out = cli_setup.uninstall_command()
    assert out.changed and not (home / ".local/bin/samta-tracker").exists() and exe.exists()
    assert not cli_setup.uninstall_command().changed


def test_without_the_program_install_fails_plainly(monkeypatch):
    monkeypatch.setattr(cli_setup, "cli_executable", lambda: None)
    with pytest.raises(cli_setup.SetupError):
        cli_setup.install_command()


def test_windows_path_editing_is_exact_and_case_insensitive():
    new, changed = cli_setup.path_with_dir(r"C:\a;C:\b", r"C:\app")
    assert changed and new == r"C:\a;C:\b;C:\app"
    again, changed = cli_setup.path_with_dir(new, r"C:\app")
    assert not changed and again == new
    back, changed = cli_setup.path_without_dir(new, r"C:\app")
    assert changed and back == r"C:\a;C:\b"
    assert cli_setup.path_without_dir(back, r"C:\app")[1] is False


def test_setup_command_installs_link_and_skill(fake_install):
    home, _ = fake_install
    result = runner.invoke(app, ["--json", "setup"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert "Installed" in data["command"] and data["skill"].startswith("installed")
    assert (home / ".claude/skills/samta-tracker/SKILL.md").exists()


def test_setup_no_skill_and_undo(fake_install):
    home, _ = fake_install
    assert runner.invoke(app, ["setup", "--no-skill"]).exit_code == 0
    assert not (home / ".claude").exists()
    assert runner.invoke(app, ["setup", "--undo"]).exit_code == 0
    assert not (home / ".local/bin/samta-tracker").exists()


def test_settings_presenter_buttons_do_the_setup(fake_install):
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    from src.ui.settings_presenter import SettingsPresenter
    from src.ui.views.settings_view import SettingsView

    class Auth:
        pass

    home, _ = fake_install
    view = SettingsView()
    messages = []
    view.show_info = messages.append
    view.show_error = messages.append
    presenter = SettingsPresenter(view, Auth())  # keep a reference or the slots disconnect
    assert view.install_cli_btn.isEnabled() and "not installed" in view.cli_status_label.text()

    view.install_cli_btn.click()
    view.install_skill_btn.click()
    assert (home / ".local/bin/samta-tracker").is_symlink()
    assert (home / ".claude/skills/samta-tracker/SKILL.md").exists()
    assert len(messages) == 2
    assert view.install_cli_btn.text() == "Command-line tool installed"
    assert view.install_skill_btn.text() == "Agent skill installed"
