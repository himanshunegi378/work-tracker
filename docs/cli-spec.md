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
| `samta-tracker login` (alias `auth login`) | `-u/--username`, `--password-stdin`, `--url`, `--ui` | Prompts for missing username and hidden password. `--ui` opens a small credentials window instead (wrong passwords show an error and allow a retry; exit 4 if there is no display). Saved to the keyring, so the GUI is logged in too. |
| `samta-tracker logout` | | Removes the saved credentials, same as "Clear Credentials" in the GUI. |
| `samta-tracker auth status` | | Server, user, session valid or expired. |

### Read data
Shared by every `list`: `-n/--limit` (default 20 per page; with `--all`, the most rows to fetch, default 250, max 1000), `--page N`, `--all` (cannot be combined with `--page`), `-s/--search` (projects, activities). The server gives no totals, so the footer reads `20 projects shown · page 1 · more may exist (--page 2)`. `-q` prints only ids/names; `--json` prints full records.

| Command | Flags |
|---|---|
| `samta-tracker projects list` | `-s`, `--status open\|completed\|cancelled`, `--priority high\|medium\|low`, `--active/--inactive`, `-n`, `--page`, `--all` |
| `samta-tracker projects view ID` | ID or exact project name |
| `samta-tracker activities list` | `-s`, `-n`, `--page`, `--all` |
| `samta-tracker timesheets list` | `--status draft\|submitted\|billed\|payslip\|completed\|cancelled`, `--workflow-state TEXT`, `--from DATE`, `--to DATE`, `--employee ID`, `-n`, `--page`, `--all` |
| `samta-tracker timesheets view NAME` | `--no-logs` (time logs are shown by default) |
| `samta-tracker timesheets today` | `--date DATE`, `--no-logs` |

Dates accept `YYYY-MM-DD`, `today`, `yesterday`, `tomorrow`, `-7d`, `+3d`, `-2w`, or a weekday name (the most recent one on or before today).
`timesheets today` finds the timesheet whose range covers the date, shows the day's logs and the hours logged that day; exit 1 if none covers it.
Time-log tables shorten the description to the terminal width; `--json` is never truncated.

### Log time (same save logic as the GUI Smart Log)
```
samta-tracker log add -p PROJ-0012 -a "Development" -d "Fixed invoice rounding"
                      [--duration 1h30m] [--billable | --no-billable]
                      [--date DATE --at TIME] [--recent] [--dry-run]
samta-tracker log list [--date DATE | --timesheet NAME]
```
- `-p` and `-a` accept an id or name (case-insensitive); an ambiguous match lists the candidates and asks for the exact one. Missing `-p/-a/-d` are prompted in a terminal; without a terminal they are usage errors (exit 2).
- **Timing:** a new entry starts one second after your previous entry that day and ends at the end time. With no previous entry that day it ends now and is `--duration` long (default: the `interval` setting, 15m). With `--duration`, the entry starts right after your previous one and runs that long (it must not end in the future). `--at TIME` fixes the end time and needs `--duration`. `--date` for a past day needs `--at` and `--duration`; future dates are rejected. If your previous entry forces a different length than `--duration`, the preview says so.
- **Merging:** an entry with the same project, activity, description and billing as your previous one extends it instead of adding a row (the preview says "extends your previous entry").
- `--billable/--no-billable` default to your last entry's value for the same project and activity, else no. `--recent` picks a recent project/activity pair (terminal only).
- **Safety:** `--dry-run` prints exactly what would be saved and saves nothing. In a terminal the entry is shown and confirmed (`Save this entry? [Y/n]`); `-y` skips confirmations. The server rejects overlapping entries.
- Output: `✓ Logged 1h on PROJ-0007 / Execution in TS-2026-07228 (total today: 4h)`. `--json` returns the saved summary.
- `log list` shows entries for a day (default today) or for a whole timesheet, with a total. Tables show times to the minute; `--json` carries the raw server values. The server stores each row's hours to 2 decimals, so row hours can differ slightly from the exact timesheet total.
- Later: `log edit`, `log rm`.

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
1. **Auth and config** (done): `login`, `logout`, `auth status`, `config get|set` (url, theme, interval), shared preferences file. The session cookies are stored in the OS keyring (`SessionStore`) so the GUI and the CLI share one server-side session; without a keyring each side logs in on its own.
2. **Read commands** (done): `projects list|view`, `activities list`, `timesheets list|view|today`, with paging, `--all`, filters and relative dates.
3. **Log time** (done): `log add` (flags, prompts, `--recent`, `--duration`, `--at`, `--dry-run`) and `log list`.
4. **GUI tracker control**: single instance, local socket protocol, tray icon, `--hidden`, shared reminder interval.
5. **Tracker commands**: `start`, `stop`, `status`, `gui`, `remind` fallback, `data.refresh` after CLI saves.
6. **Parity, packaging and extras**: GUI/CLI parity test, shell completion, PyInstaller for both entry points, then edit/delete/submit.

## Open points
- Tray support varies on Linux. Some GNOME setups need an extension for tray icons. If the tray is unavailable, `--hidden` falls back to a minimized window.
- Console script is `samta-tracker`. It has no clash with GNOME's `tracker` search tool. A short alias (e.g. `st`) can be added later.
