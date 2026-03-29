import os
import sys
from pathlib import Path

APP_NAME = "Work Tracker"
APP_DIR_NAME = "work-tracker"
LOG_FILE_NAME = "work_tracker.log"


def app_base_path() -> Path:
    """Return the folder containing the running application."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_resource_path(*parts: str) -> Path:
    """Resolve a file that is bundled into the application image."""
    base = Path(getattr(sys, "_MEIPASS", app_base_path()))
    return base.joinpath(*parts)


def user_data_dir() -> Path:
    """Return the OS-appropriate writable directory for application data."""
    home = Path.home()

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return base / APP_NAME

    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME

    base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return base / APP_DIR_NAME


def user_log_dir() -> Path:
    """Return the OS-appropriate writable directory for log files."""
    home = Path.home()

    if sys.platform == "win32":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                os.environ.get("APPDATA", home / "AppData" / "Local"),
            )
        )
        return base / APP_NAME / "Logs"

    if sys.platform == "darwin":
        return home / "Library" / "Logs" / APP_NAME

    base = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
    return base / APP_DIR_NAME / "logs"


def projects_file_path() -> Path:
    """Return the default writable path for offline project data."""
    return user_data_dir() / "projects.json"


def logs_file_path() -> Path:
    """Return the default writable path for offline log data."""
    return user_data_dir() / "logs.json"


def log_file_path() -> Path:
    """Return the writable log file path for the packaged app."""
    return user_log_dir() / LOG_FILE_NAME


def ensure_runtime_dirs() -> None:
    """Create any writable directories the app expects before use."""
    user_data_dir().mkdir(parents=True, exist_ok=True)
    user_log_dir().mkdir(parents=True, exist_ok=True)
