"""Small credentials window used by `samta-tracker login --ui`.

The dialog verifies the credentials itself (off the UI thread) so a wrong
password shows an error and lets the user retry instead of closing.
"""

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from src.ui.design import SPACE, button, label

logger = logging.getLogger(__name__)

# verify(username, password) -> True when the server accepted the login
Verify = Callable[[str, str], bool]


class _Signals(QObject):
    done = Signal(bool, str)  # ok, error message


class _VerifyWorker(QRunnable):
    def __init__(self, verify: Verify, username: str, password: str):
        super().__init__()
        self.verify, self.username, self.password = verify, username, password
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            ok = self.verify(self.username, self.password)
            self.signals.done.emit(bool(ok), "" if ok else "Login failed. Check your username and password.")
        except Exception as exc:  # noqa: BLE001 - shown to the user in the dialog
            logger.exception("Login verification failed")
            self.signals.done.emit(False, str(exc) or exc.__class__.__name__)


class LoginDialog(QDialog):
    """Ask for username + password and verify them before closing."""

    def __init__(self, verify: Verify, server: str = "", username: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._verify = verify
        self._worker: Optional[_VerifyWorker] = None
        self.logged_in_user: Optional[str] = None
        self.setWindowTitle("Work Tracker: Log in")
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        layout.setSpacing(SPACE["md"])

        layout.addWidget(label("Log in", "title"))
        if server:
            layout.addWidget(label(server, "caption"))

        self.username_input = QLineEdit(username)
        self.username_input.setPlaceholderText("Username or email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(
            lambda on: self.password_input.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.show_password)

        self.status = label("", "caption", tone="danger")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addStretch()
        self.cancel_btn = button("Cancel", "secondary")
        self.login_btn = button("Log in", "primary")
        self.login_btn.setDefault(True)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.login_btn)
        layout.addLayout(row)

        self.cancel_btn.clicked.connect(self.reject)
        self.login_btn.clicked.connect(self._submit)
        self.password_input.returnPressed.connect(self._submit)
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        (self.password_input if username else self.username_input).setFocus()

    # -- behaviour ---------------------------------------------------------
    def _show_error(self, message: str) -> None:
        self.status.setText(message)
        self.status.show()

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.username_input, self.password_input, self.login_btn, self.show_password):
            widget.setEnabled(not busy)
        self.login_btn.setText("Logging in…" if busy else "Log in")

    @Slot()
    def _submit(self) -> None:
        if self._worker is not None:  # already verifying
            return
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self._show_error("Enter both username and password.")
            return
        self.status.hide()
        self._set_busy(True)
        self._worker = _VerifyWorker(self._verify, username, password)
        self._worker.signals.done.connect(lambda ok, msg, u=username: self._finished(ok, msg, u))
        QThreadPool.globalInstance().start(self._worker)

    def _finished(self, ok: bool, message: str, username: str) -> None:
        self._worker = None
        self._set_busy(False)
        if ok:
            self.logged_in_user = username
            self.password_input.clear()
            self.accept()
        else:
            self._show_error(message)
            self.password_input.selectAll()
            self.password_input.setFocus()

    def reject(self) -> None:
        if self._worker is None:  # ignore Cancel/Esc while a check is running
            super().reject()
