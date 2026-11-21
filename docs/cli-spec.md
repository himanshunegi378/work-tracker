# `samta-tracker` CLI: Specification (v1 draft)

The CLI and the GUI are two front ends of **one application**. Both call the same
core (`src/core`), share the same login (OS keyring), server URL and preferences,
and write to the same server timesheets. A feature is not done until it exists in
the core, the GUI and the CLI.

```
   GUI (PySide6)  <──── local socket (start/stop/status/show) ────>  CLI (tracker)
        \                                                          /
         └────────────── src/core (shared use-cases) ─────────────┘
                     services/ · ApiClient · keyring · prefs
```

Data commands (projects, timesheets, log...) call the core directly and need no GUI.
Only tracker control (`start`, `stop`, `status`, `gui`) talks to the running GUI.

## Global flags
`--json` · `--no-color` · `-y/--yes` · `-q/--quiet` · `-h/--help` · `--version`

Exit codes: `0` ok · `1` error · `2` bad usage · `3` not logged in · `4` GUI unavailable (no display / failed to start)

## Commands

### Auth
| Command | Flags | Notes |
|---|---|---|
| `samta-tracker login` (alias `auth login`) | `-u/--username`, `--password-stdin`, `--url` | Prompts for missing username and hidden password. Saved to the keyring, so the GUI is logged in too. |
| `samta-tracker logout` | `--forget` | `--forget` also deletes saved credentials. |
| `samta-tracker auth status` | | Server, user, session valid or expired. |

### Read data
| Command | Flags |
|---|---|
| `samta-tracker projects list` | `-s TEXT`, `--status open\|completed\|cancelled`, `--priority high\|medium\|low`, `-n 20`, `--page N` |
| `samta-tracker projects view ID` | |
| `samta-tracker activities list` | `-s TEXT`, `-n`, `--page` |
| `samta-tracker timesheets list` | `--status`, `--from/--to DATE`, `-n`, `--page` |
| `samta-tracker timesheets view NAME` | `--logs` |
| `samta-tracker timesheets today` | |

### Log time (same behaviour as the GUI Smart Log)
```
samta-tracker log add -p PROJ-0012 -a "Development" -d "Fixed invoice rounding"
                [--duration 1h30m] [--billable | --no-billable] [--date YYYY-MM-DD] [--recent]
samta-tracker log list [--timesheet NAME | --today]
```
- Missing `-p/-a/-d` are prompted. `--recent` picks from recent project/activity pairs.
- Without `--duration`, the interval is the time since the last log (as in the GUI).
- If the GUI is open, the CLI tells it to refresh its dashboard after a save.

### Tracker control (talks to the GUI)
| Command | Flags | Behaviour |
|---|---|---|
| `samta-tracker start` | `--every 15m`, `--hidden` (default) / `--show` | If the GUI isn't running, launch it to the **system tray** and wait for it (10 s). Then start the tracker. If already running, just start the tracker. |
| `samta-tracker stop` | `--quit` | Stop the tracker. If the CLI launched the GUI and the window was never opened, quit it too. `--quit` always quits. |
| `samta-tracker status` | | User, tracker state (active/inactive, next prompt in N min), GUI running or not, project and timesheet counts. |
| `samta-tracker gui` | | Open the window, or raise it if already running. |
| `samta-tracker remind` | `--every 15m` | **Fallback for no-display sessions (SSH, CI).** Foreground reminders in the terminal, saved through `log add`. |

With no display available, `start/stop/gui` exit with code 4 and suggest `samta-tracker remind`.

### Config
`samta-tracker config get|set <key> [value]` with keys `url`, `theme` (`light|dark`), `interval` (reminder interval).
Shared with the GUI Settings screen.

### Later (add to GUI and CLI together)
`projects create|edit` · `log edit|rm` · `timesheets submit`. These need new backend calls
and new GUI screens.

## GUI changes required for tracker control
1. **Single instance**: a `QLocalServer` named per user. A second launch hands off to the first instead of opening a second window.
2. **IPC protocol**: JSON lines over the socket: `tracker.start {every}`, `tracker.stop`, `tracker.status`, `window.show`, `app.quit`, `data.refresh`. The socket is user-only (0600 / per-user named pipe).
3. **System tray**: `QSystemTrayIcon` with Open / Start-Stop tracker / Quit. Closing the window while the tracker is active minimizes to the tray.
4. **`--hidden` launch flag** on `gui_main.py` (start without showing the window).
5. **Reminder interval** setting (default 15 min), used by both the GUI toggle and `samta-tracker start --every`.

## What was removed
The old local-JSON CLI (`main.py`, `ProjectManager`, `LogManager`, `JSONStorage`, the old prompt handler) and
the unused legacy views and presenter. That was a separate data store (done in Phase 0).

## Install and run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .              # installs `samta-tracker` and `work-tracker-gui`
samta-tracker --help
python gui_main.py            # or: work-tracker-gui
```

## Delivery plan
0. **Foundation** (done): `src/core` (`build_app()` shared wiring, logging), `src/cli` skeleton (global flags, output helpers, exit codes), `pyproject.toml` with the `samta-tracker` entry point, GUI refactored onto the core, old CLI removed.
1. **Auth and config**: `login`, `logout`, `auth status`, `config get|set` (url, theme, interval), shared preferences, session-cookie persistence.
2. **Read commands**: `projects list|view`, `activities list`, `timesheets list|view|today`.
3. **Log time**: `log add` (flags, prompts, `--recent`, `--duration`) and `log list`.
4. **GUI tracker control**: single instance, local socket protocol, tray icon, `--hidden`, shared reminder interval.
5. **Tracker commands**: `start`, `stop`, `status`, `gui`, `remind` fallback, `data.refresh` after CLI saves.
6. **Parity, packaging and extras**: GUI/CLI parity test, shell completion, PyInstaller for both entry points, then edit/delete/submit.

## Open points
- Tray support varies on Linux. Some GNOME setups need an extension for tray icons. If the tray is unavailable, `--hidden` falls back to a minimized window.
- Console script is `samta-tracker`. It has no clash with GNOME's `tracker` search tool. A short alias (e.g. `st`) can be added later.
