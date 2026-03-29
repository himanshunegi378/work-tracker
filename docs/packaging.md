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
  - `worktracker-ubuntu` as `worktracker-ubuntu.tar.gz`
  - `worktracker-windows` as `worktracker-windows.zip`
  - `worktracker-macos` as `worktracker-macos.zip`
- Artifacts are available from the GitHub Actions run summary page for each successful workflow run.
- Latest downloadable builds are also published to `artifacts/desktop/` on the `main` branch.
- The tracked `artifacts/desktop/` folder is refreshed on each successful push to `main`.
- CI artifacts are unsigned in this phase; release publishing, signing, and notarization are out of scope.

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
