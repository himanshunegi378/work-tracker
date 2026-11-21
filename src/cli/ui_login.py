"""Open the desktop credentials window for `samta-tracker login --ui`.

PySide6 is imported lazily so every other CLI command stays fast.
"""

import os
import sys
from typing import Callable, Optional

from src.cli.errors import GUI_UNAVAILABLE, CliError


def display_available() -> bool:
    """True when a graphical session is reachable (always true on Windows/macOS)."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def prompt_login_ui(
    verify: Callable[[str, str], bool],
    server: str = "",
    username: str = "",
) -> Optional[str]:
    """Show the login window. Returns the username on success, None if cancelled."""
    if not display_available():
        raise CliError(
            "No display available, so the login window can't open.",
            GUI_UNAVAILABLE,
            hint="Use `samta-tracker login -u USER --password-stdin` instead.",
        )

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")

    from src.ui.design import apply_theme
    from src.ui.views.login_dialog import LoginDialog

    apply_theme(app)
    dialog = LoginDialog(verify, server=server, username=username)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    accepted = dialog.exec() == LoginDialog.Accepted
    return dialog.logged_in_user if accepted else None
