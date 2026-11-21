"""Start the desktop app from the CLI and wait until it can be controlled."""

import subprocess
import sys
import time
from pathlib import Path
from typing import List

from src.cli.errors import ERROR, GUI_UNAVAILABLE, CliError
from src.cli.ui_login import display_available
from src.core import ipc

STARTUP_TIMEOUT = 10.0


def gui_command(hidden: bool) -> List[str]:
    """The command line that starts the desktop app."""
    extra = ["--hidden"] if hidden else []
    if getattr(sys, "frozen", False):  # packaged build: the GUI executable sits next to this one
        exe = Path(sys.executable).with_name("WorkTracker.exe" if sys.platform == "win32" else "WorkTracker")
        return [str(exe), *extra]
    return [sys.executable, "-c", "import sys, gui_main; sys.exit(gui_main.main(sys.argv[1:]))", *extra]


def launch_gui(hidden: bool) -> subprocess.Popen:
    """Start the app detached from this terminal, so closing the terminal doesn't kill it."""
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(gui_command(hidden), **options)


def require_display() -> None:
    if not display_available():
        raise CliError(
            "No display available, so the desktop app can't start.",
            GUI_UNAVAILABLE,
            hint="Use `samta-tracker remind` to get reminders in this terminal instead.",
        )


def ensure_gui(hidden: bool = True, timeout: float = STARTUP_TIMEOUT) -> bool:
    """Make sure the desktop app is running. Returns True if this call launched it."""
    if ipc.is_running():
        return False
    require_display()
    process = launch_gui(hidden)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ipc.is_running():
            return True
        if process.poll() is not None:
            raise CliError(
                f"The desktop app exited right after starting (code {process.returncode}).", ERROR,
                hint="Check the log: ~/.local/state/work-tracker/logs/work_tracker.log",
            )
        time.sleep(0.2)
    raise CliError(f"The desktop app did not start within {int(timeout)}s.", ERROR)


def wait_until_stopped(timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not ipc.is_running():
            return True
        time.sleep(0.2)
    return False
