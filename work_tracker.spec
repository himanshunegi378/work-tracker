import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve()
icon_path = project_root / "assets" / "work_tracker.ico"
icon = str(icon_path) if icon_path.exists() else None

hiddenimports = collect_submodules("src") + collect_submodules("keyring.backends")
datas = copy_metadata("keyring")


def analyze(script):
    return Analysis(
        [script],
        pathex=[str(project_root)],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=[],
        noarchive=False,
        optimize=0,
    )


# Two programs share one folder so `samta-tracker start` finds `WorkTracker` next to it:
#   WorkTracker    the desktop app (no console window)
#   samta-tracker  the command line (console; needs Qt only for `login --ui`)
gui_a = analyze("gui_main.py")
cli_a = analyze("samta_tracker_cli.py")
MERGE((gui_a, "WorkTracker", "WorkTracker"), (cli_a, "samta-tracker", "samta-tracker"))

gui_exe = EXE(
    PYZ(gui_a.pure),
    gui_a.scripts,
    [],
    name="WorkTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    exclude_binaries=True,
)

cli_exe = EXE(
    PYZ(cli_a.pure),
    cli_a.scripts,
    [],
    name="samta-tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    exclude_binaries=True,
)

coll = COLLECT(
    gui_exe,
    gui_a.binaries,
    gui_a.datas,
    cli_exe,
    cli_a.binaries,
    cli_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WorkTracker",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="WorkTracker.app",
        icon=icon,
        bundle_identifier="com.worktracker.app",
    )
