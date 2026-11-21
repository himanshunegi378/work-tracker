import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtWidgets import QApplication

from src.core import ipc, prefs


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")
    import gui_main

    auth = MagicMock()
    auth.get_saved_username.return_value = None
    auth.get_saved_password.return_value = None
    projects = MagicMock()
    projects.get_projects.return_value = []
    timesheets = MagicMock()
    timesheets.get_timesheets.return_value = []
    win = gui_main.MainWindow(auth, projects, MagicMock(), timesheets)
    yield win
    win.tracker.stop()
    win.close()


def test_ping_and_unknown_command(window):
    assert window.handle_ipc("ping", {})["pid"] == os.getpid()
    with pytest.raises(ipc.IpcCommandError):
        window.handle_ipc("tracker.reboot", {})


def test_start_updates_the_dashboard_button_and_status(window):
    status = window.handle_ipc("tracker.start", {"every": 600})
    assert status["tracker"]["active"] is True and status["tracker"]["interval_seconds"] == 600
    dash = window.container.dash_view
    assert dash.start_btn.text() == "STOP TRACKER" and dash.tracker_title.text() == "Work Tracker: ACTIVE"
    window.handle_ipc("tracker.stop", {})
    assert dash.start_btn.text() == "START TRACKER"


def test_dashboard_button_and_cli_share_one_tracker(window):
    window.container.dash_view.start_btn.click()
    assert window.handle_ipc("tracker.status", {})["tracker"]["active"] is True
    window.handle_ipc("tracker.stop", {})
    assert window.container.dash_view.start_btn.text() == "START TRACKER"


@pytest.mark.parametrize("bad", [5, 999999, "900", True, 1.5])
def test_start_rejects_bad_intervals(window, bad):
    with pytest.raises(ipc.IpcCommandError):
        window.handle_ipc("tracker.start", {"every": bad})
    assert window.tracker.active is False


def test_start_without_every_uses_the_saved_setting(window):
    prefs.set_value("interval", "25m")
    assert window.handle_ipc("tracker.start", {})["tracker"]["interval_seconds"] == 1500


def test_window_show_makes_it_visible(window):
    window.hide()
    window.handle_ipc("window.show", {})
    assert window.isVisible()
    assert window.handle_ipc("tracker.status", {})["window_visible"] is True


def test_closing_without_a_tray_quits_even_while_tracking(window, monkeypatch):
    quits = []
    monkeypatch.setattr("gui_main.QApplication.quit", lambda: quits.append(1))
    window.tracker.start(600)
    window.close()
    assert quits and window.tracker.active is False


def test_closing_with_a_tray_hides_instead_while_the_tracker_runs(window, monkeypatch):
    quits = []
    monkeypatch.setattr("gui_main.QApplication.quit", lambda: quits.append(1))
    window.tray = MagicMock()
    window.show()
    window.tracker.start(600)
    window.close()
    assert quits == [] and window.isVisible() is False and window.tracker.active is True
    window.tray.notify.assert_called_once()
    window.tray = None  # fixture teardown closes for real


def test_closing_with_a_tray_but_no_tracker_quits(window, monkeypatch):
    quits = []
    monkeypatch.setattr("gui_main.QApplication.quit", lambda: quits.append(1))
    window.tray = MagicMock()
    window.close()
    assert quits


def test_dashboard_set_tracking_does_not_emit_the_toggle_signal(window):
    emitted = []
    window.container.dash_view.tracker_toggle_requested.connect(emitted.append)
    window.container.dash_view.set_tracking(True)
    assert emitted == [] and window.container.dash_view.start_btn.text() == "STOP TRACKER"
    window.container.dash_view.set_tracking(False)


def test_parse_args_hidden_flag_and_qt_options_are_ignored():
    import gui_main

    assert gui_main.parse_args([]).hidden is False
    assert gui_main.parse_args(["--hidden"]).hidden is True
    assert gui_main.parse_args(["--hidden", "-platform", "offscreen"]).hidden is True
