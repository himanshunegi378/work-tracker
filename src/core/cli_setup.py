"""Make the `samta-tracker` command usable from any terminal, and install the agent skill.

Shared by `samta-tracker setup` and the desktop app's Settings screen, so both do the same thing.
Nothing here needs admin rights: it only touches the current user's folders and PATH.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import List, Optional, Tuple

COMMAND = "samta-tracker"
SKILL_NAME = "samta-tracker"
SKILL_INSTALL_COMMAND = "npx skills add himanshunegi378/work-tracker"  # skills.sh installer


class SetupError(Exception):
    """A setup step could not be done; the message says why in plain words."""


@dataclass
class Outcome:
    message: str
    changed: bool = True
    restart_terminal: bool = False
    hint: Optional[str] = None


# ── locating things ───────────────────────────────────────────────────────────

def _exe_name() -> str:
    return COMMAND + (".exe" if sys.platform == "win32" else "")


def cli_executable() -> Optional[Path]:
    """The samta-tracker program that belongs to this installation, if there is one."""
    # Do not resolve(): in a virtualenv, python is a symlink into the system install, not next to the script.
    here = Path(sys.executable).parent
    candidate = here / _exe_name()  # packaged build: next to WorkTracker; source install: venv bin
    return candidate if candidate.exists() else None


def link_dir() -> Path:
    return Path.home() / ".local" / "bin"


def link_path() -> Path:
    return link_dir() / COMMAND


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.expanduser(p.strip().strip('"'))))


def path_entries(path_value: Optional[str] = None) -> List[str]:
    value = os.environ.get("PATH", "") if path_value is None else path_value
    return [e for e in value.split(os.pathsep) if e.strip()]


def dir_on_path(directory: Path, path_value: Optional[str] = None) -> bool:
    return _norm(str(directory)) in {_norm(e) for e in path_entries(path_value)}


def is_installed() -> bool:
    """True if typing `samta-tracker` in a new terminal should work."""
    exe = cli_executable()
    if exe is None:
        return shutil.which(COMMAND) is not None
    if sys.platform == "win32":
        return dir_on_path(exe.parent, _windows_user_path() or "") or dir_on_path(exe.parent)
    link = link_path()
    return link.is_symlink() and link.resolve() == exe.resolve()


# ── the command on PATH ───────────────────────────────────────────────────────

def install_command() -> Outcome:
    exe = cli_executable()
    if exe is None:
        raise SetupError("The command-line program was not found next to this app.")
    if sys.platform == "win32":
        return _install_windows(exe)
    return _install_posix(exe)


def uninstall_command() -> Outcome:
    exe = cli_executable()
    if sys.platform == "win32":
        return _uninstall_windows(exe)
    link = link_path()
    if link.is_symlink():
        link.unlink()
        return Outcome(f"Removed {link}.")
    return Outcome("The command was not installed.", changed=False)


def _install_posix(exe: Path) -> Outcome:
    link = link_path()
    if link.is_symlink() and link.resolve() == exe.resolve():
        outcome = Outcome(f"Already installed: {link}", changed=False)
    else:
        if link.exists() and not link.is_symlink():
            raise SetupError(f"{link} already exists and is not a link made by this app; leaving it alone.")
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()  # an old link, e.g. to a previous install location
        try:
            link.symlink_to(exe)
        except OSError as exc:
            raise SetupError(f"Could not create {link}: {exc}")
        outcome = Outcome(f"Installed: {link} -> {exe}")
    if not dir_on_path(link.parent):
        outcome.restart_terminal = True
        outcome.hint = (f"{link.parent} is not on your PATH yet. Add this line to your shell profile "
                        f"(~/.bashrc or ~/.zshrc), then open a new terminal:\n"
                        f'  export PATH="$HOME/.local/bin:$PATH"')
    return outcome


def path_with_dir(current: str, directory: str) -> Tuple[str, bool]:
    """Windows-style PATH text with `directory` added; second value says whether it changed."""
    parts = [p for p in current.split(";") if p.strip()]
    if _norm(directory) in {_norm(p) for p in parts}:
        return current, False
    return ";".join(parts + [directory]), True


def path_without_dir(current: str, directory: str) -> Tuple[str, bool]:
    parts = [p for p in current.split(";") if p.strip()]
    kept = [p for p in parts if _norm(p) != _norm(directory)]
    return ";".join(kept), len(kept) != len(parts)


def _windows_user_path() -> Optional[str]:
    if sys.platform != "win32":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, "Path")[0]
    except FileNotFoundError:
        return ""


def _write_windows_user_path(value: str) -> None:
    import ctypes
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)
    try:  # tell running programs (Explorer) the environment changed
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 2000, None)
    except Exception:  # noqa: BLE001 - best effort; a new login always works
        pass


def _install_windows(exe: Path) -> Outcome:
    new, changed = path_with_dir(_windows_user_path() or "", str(exe.parent))
    if not changed:
        return Outcome("Already on your PATH.", changed=False)
    _write_windows_user_path(new)
    return Outcome(f"Added {exe.parent} to your PATH.", restart_terminal=True)


def _uninstall_windows(exe: Optional[Path]) -> Outcome:
    if exe is None:
        return Outcome("The command was not installed.", changed=False)
    new, changed = path_without_dir(_windows_user_path() or "", str(exe.parent))
    if not changed:
        return Outcome("The command was not installed.", changed=False)
    _write_windows_user_path(new)
    return Outcome(f"Removed {exe.parent} from your PATH.", restart_terminal=True)


# ── the agent skill ───────────────────────────────────────────────────────────

def skill_text() -> str:
    return resources.files("src.cli.skill").joinpath("SKILL.md").read_text(encoding="utf-8")


def skill_path(skills_dir: Optional[Path] = None) -> Path:
    base = skills_dir.expanduser() if skills_dir else Path.home() / ".claude" / "skills"
    return base / SKILL_NAME / "SKILL.md"


def skill_status(skills_dir: Optional[Path] = None) -> str:
    """`missing`, `outdated` or `current`."""
    dest = skill_path(skills_dir)
    if not dest.exists():
        return "missing"
    return "current" if dest.read_text(encoding="utf-8") == skill_text() else "outdated"


def install_skill(skills_dir: Optional[Path] = None, force: bool = False) -> Tuple[str, Path]:
    """Copy the skill into place. Returns (`installed`|`updated`|`up-to-date`, path)."""
    dest = skill_path(skills_dir)
    status = skill_status(skills_dir)
    if status == "current":
        return "up-to-date", dest
    if status == "outdated" and not force:
        raise SetupError(f"{dest} already exists and differs.")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(skill_text(), encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"Could not write {dest}: {exc}")
    return ("updated" if status == "outdated" else "installed"), dest
