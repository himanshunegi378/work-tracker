import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from src.ui.views.login_dialog import LoginDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _wait(qapp, dialog):
    """Let the worker finish and deliver its signal to the dialog."""
    QThreadPool.globalInstance().waitForDone(3000)
    for _ in range(5):
        qapp.processEvents()


def test_success_accepts_and_clears_password(qapp):
    calls = []
    dialog = LoginDialog(lambda u, p: calls.append((u, p)) or True, server="matrix.samta.ai")
    dialog.username_input.setText(" jane@samta.ai ")
    dialog.password_input.setText("s3cret")
    dialog._submit()
    _wait(qapp, dialog)
    assert calls == [("jane@samta.ai", "s3cret")]
    assert dialog.result() == QDialog.Accepted and dialog.logged_in_user == "jane@samta.ai"
    assert dialog.password_input.text() == ""


def test_wrong_password_shows_error_and_stays_open(qapp):
    dialog = LoginDialog(lambda u, p: False)
    dialog.username_input.setText("jane")
    dialog.password_input.setText("bad")
    dialog._submit()
    _wait(qapp, dialog)
    assert dialog.result() != QDialog.Accepted and dialog.logged_in_user is None
    assert not dialog.status.isHidden() and "Login failed" in dialog.status.text()
    assert dialog.login_btn.isEnabled() and dialog.password_input.isEnabled()


def test_exception_message_is_shown(qapp):
    def boom(u, p):
        raise RuntimeError("Server unreachable")

    dialog = LoginDialog(boom)
    dialog.username_input.setText("a")
    dialog.password_input.setText("b")
    dialog._submit()
    _wait(qapp, dialog)
    assert "Server unreachable" in dialog.status.text() and dialog.logged_in_user is None


def test_empty_fields_do_not_call_verify(qapp):
    calls = []
    dialog = LoginDialog(lambda u, p: calls.append(1) or True)
    dialog.username_input.setText("jane")
    dialog._submit()
    assert calls == [] and "both" in dialog.status.text()


def test_prefill_and_show_password_toggle(qapp):
    dialog = LoginDialog(lambda u, p: True, username="jane@samta.ai")
    assert dialog.username_input.text() == "jane@samta.ai"
    assert dialog.password_input.echoMode() == QLineEdit.Password
    dialog.show_password.setChecked(True)
    assert dialog.password_input.echoMode() == QLineEdit.Normal


def test_cancel_rejects(qapp):
    dialog = LoginDialog(lambda u, p: True)
    dialog.cancel_btn.click()
    assert dialog.result() == QDialog.Rejected and dialog.logged_in_user is None
