import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve()
icon_path = project_root / "assets" / "work_tracker.ico"
icon = str(icon_path) if icon_path.exists() else None

hiddenimports = collect_submodules("src") + collect_submodules("keyring.backends")
datas = copy_metadata("keyring")


a = Analysis(
    ["gui_main.py"],
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
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

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="WorkTracker.app",
        icon=icon,
        bundle_identifier="com.worktracker.app",
    )
    coll = COLLECT(
        app,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="WorkTracker",
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="WorkTracker",
    )
