# Packaging Work Tracker

## Requirements
- Python 3.12
- OS-native build host for the target bundle
- `venv` support available in the local Python install

## Build Commands
- Linux: `bash scripts/build_linux.sh`
- macOS: `bash scripts/build_macos.sh`
- Windows PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`

Each script bootstraps a repo-local `.venv`, installs runtime dependencies plus `pyinstaller`, and builds the GUI bundle from `work_tracker.spec`.

## CI Builds
- GitHub Actions workflow: `.github/workflows/build-desktop.yml`
- Trigger: pushes to `main` only
- Platforms: Ubuntu, Windows, and macOS
- CI flow: set up Python 3.12, run `python -m unittest discover -s tests`, then build the desktop bundle with the existing platform script
- Workflow artifacts:
  - `worktracker-deb` as `worktracker-ubuntu.deb` (Debian/Ubuntu package; no tar.gz is built for Linux)
  - `worktracker-windows` as `worktracker-windows.zip`
  - `worktracker-macos` as `worktracker-macos.zip`
- Artifacts are available from the GitHub Actions run summary page for each successful workflow run.
- Latest downloadable builds are also published to `artifacts/desktop/` on the dedicated `artifacts` branch.
- The `artifacts` branch is created automatically on the first successful publish if it does not already exist.
- The tracked `artifacts/desktop/` folder on that branch is refreshed on each successful push to `main`.
- CI artifacts are unsigned in this phase; release publishing, signing, and notarization are out of scope.

## Debian/Ubuntu package
- `bash scripts/build_deb.sh [out_dir]` builds `work-tracker_<version>_<arch>.deb` from `dist/WorkTracker` (run `build_linux.sh` first). CI builds it as `worktracker-ubuntu.deb`.
- Install or upgrade: `sudo apt install ./worktracker-ubuntu.deb` (installing a newer package over the old one upgrades it; no manual removal). Remove: `sudo apt remove work-tracker`.
- Installs to `/opt/work-tracker`, links `samta-tracker` and `work-tracker` into `/usr/bin` (so the command works in any terminal with no `setup`), and adds a desktop-menu entry. The menu entry has no custom icon yet.
- **glibc:** a PyInstaller bundle is not independent of glibc: it needs at least the glibc of the build machine. CI therefore builds on `ubuntu-22.04` (glibc 2.35), so the `.deb` runs on Ubuntu 22.04+ and Debian 12+. `build_deb.sh` reads the real requirement from the binaries, writes `Depends: libc6 (>= X)` (apt refuses an older system with a clear message) and fails the build if `MAX_GLIBC` is exceeded. To support older systems, build on an older distribution.
- Per-user data (saved login in the keyring, settings, logs) lives outside the package and survives upgrades and removal.

## Output
- Linux and Windows bundle folder: `dist/WorkTracker`
- macOS app bundle: `dist/WorkTracker.app`
- macOS support folder: `dist/WorkTracker/`
- Intermediate build folder: `build/`

## Runtime Storage
- App data is stored in the user's OS-specific application-data directory.
- Logs are written to the user's OS-specific log directory.
- Credentials remain in the system keychain via `keyring` under the `work-tracker` service name.

## Smoke Test Checklist
- Launch the bundled app without a terminal window.
- Confirm the app creates writable data and log directories on first run.
- Log in successfully and restart the app to verify remembered credentials.
- Navigate Projects, Activities, Timesheets, and Settings.
- Trigger the smart-log dialog and confirm save/background refresh still work.

## Notes
- Cross-compilation is not supported in this setup; build each artifact on its target OS.
- If you add a real app icon later, place it at `assets/work_tracker.ico` before building Windows bundles.
