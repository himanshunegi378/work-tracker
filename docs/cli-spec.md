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

### Tracker control (talks to the desktop app)
| Command | Flags | Behaviour |
|---|---|---|
| `samta-tracker start` | `--every 15m`, `--show` | If the app isn't running, launch it detached in the **system tray** (waits up to 10 s; fails fast if it exits). Then start the tracker. `--every` overrides the saved `interval` for this run. `--show` also opens the window. |
| `samta-tracker stop` | `--quit` | Stop the tracker. If the CLI started the app and nobody ever opened its window, close it too. `--quit` always closes it. Idempotent: exits 0 with a note if the app isn't running. |
| `samta-tracker status` | | User, server, whether the app is running (tray / window), tracker state with the next prompt time, project count, and timesheet rows (latest 20), the same numbers as the dashboard. Exits 0 even when logged out. |
| `samta-tracker gui` | | Open the window, or bring it forward if the app is already running. |
| `samta-tracker remind` | `--every 15m` | **Fallback for sessions without a display.** Foreground reminders in this terminal (bell + "Log it now?"), saved through `log add` (recent entries first). Waits one interval before the first reminder. Needs a terminal; Ctrl+C stops. |

With no display available, `start` and `gui` exit with code 4 and suggest `samta-tracker remind`.
After a successful `log add`, the CLI asks a running desktop app to refresh its dashboard.
The first prompt after `start` opens immediately (as with the dashboard button), then repeats every interval.

### Config and completion
- `samta-tracker config get [KEY]` and `samta-tracker config set KEY VALUE` with keys `url`, `theme` (`light|dark`), `interval` (reminder interval, 1m to 24h). Shared with the GUI: the GUI Settings screen sets `theme`; `url` and `interval` can currently only be changed from the CLI.
- `samta-tracker completion SHELL [--install]` prints (or installs for your user) tab-completion for `bash`, `zsh`, `fish` or `powershell`. Try `eval "$(samta-tracker completion bash)"`. It completes commands, flags, enum values (`--status`, `--priority`), and `config` keys and theme values. `--install-completion` / `--show-completion` also work for the current shell.

### Change and delete (Pending timesheets only)
```
samta-tracker log edit ENTRY [-d TEXT] [-a ACTIVITY] [-p PROJECT] [--billable|--no-billable]
                             [--from TIME] [--to TIME] [--timesheet NAME | --date DATE] [--dry-run]
samta-tracker log rm ENTRY [--timesheet NAME | --date DATE] [--dry-run]
samta-tracker timesheets submit NAME [--dry-run]
samta-tracker timesheets rm NAME [--dry-run]
```
- `ENTRY` is the `#` shown by `log list` (or `last`). The timesheet defaults to the one covering today.
- **Only timesheets in the `Pending` workflow state can be changed**; submitted or approved ones are refused with the reason. All four commands show what will change first and ask `[Y/n]` in a terminal; `-y` skips that. `rm` and `submit` never run unattended: without a terminal they refuse unless `-y` is passed. `--dry-run` shows the change and does nothing.
- `log edit` recalculates hours and totals, refuses an end time before the start, and refuses times that overlap another entry. `--from/--to` are times on the entry's own day. `log rm` refuses to remove the last entry (use `timesheets rm`).
- `timesheets submit` runs the workflow's `Submit` action (Pending to Submitted) and cannot be undone by you; `--dry-run` also reads which workflow actions you are allowed to use.
- The GUI offers the same actions on the Timesheet Detail screen: **Edit entry** (double-click a row too), **Delete entry**, **Submit timesheet**, **Delete timesheet**, enabled only for Pending timesheets.
- **Not possible with your permissions:** `projects create/edit`. The server grants no read, write or create permission on Project records (projects are only visible through the search list), so those commands are not built.

## How tracker control works (built in Phase 4)
- **Endpoint:** the app listens on `127.0.0.1` (random port) and writes `ipc.json` (`port`, `token`, `pid`, file mode 0600) in the app data folder. The CLI reads it, so a missing file or a refused connection means "app not running". Every request carries the token.
- **Protocol:** one JSON line in, one out: `{"token", "cmd", "args"}` -> `{"ok": true, "data": {...}}` or `{"ok": false, "error": "..."}`.
- **Commands:** `ping`, `tracker.start {every: seconds}`, `tracker.stop`, `tracker.status`, `window.show`, `data.refresh`, `app.quit`. `every` must be 60 to 86400 seconds; it overrides the saved `interval` for that run only.
- **Single instance:** a second `gui_main.py` launch asks the running one to show its window and exits. A crashed app's stale lock and endpoint file are replaced by the next launch.
- **Tray:** Open / Start-Stop tracker / Quit. Closing the window while the tracker runs hides it to the tray; otherwise closing quits. With no tray available, `--hidden` starts the window minimized.
- **First prompt:** starting the tracker shows the Smart Log prompt immediately (existing behaviour), then every interval.

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

## Packaged build
`scripts/build_linux.sh` (or `build_macos.sh` / `build_windows.ps1`) runs `work_tracker.spec`, which builds both programs into one folder, `dist/WorkTracker/`:
- `WorkTracker` is the desktop app (no console window).
- `samta-tracker` is the command line (console). It also bundles Qt, which `login --ui` needs.

They must stay side by side: `samta-tracker start` and `gui` launch the `WorkTracker` next to it. Verified on Linux (about 197 MB): `start`, `status`, `gui`, `stop --quit`, reading the real keyring login, and `completion`. The macOS and Windows scripts are updated but not built or tested here.

## Delivery plan
0. **Foundation** (done): `src/core` (`build_app()` shared wiring, logging), `src/cli` skeleton (global flags, output helpers, exit codes), `pyproject.toml` with the `samta-tracker` entry point, GUI refactored onto the core, old CLI removed.
1. **Auth and config** (done): `login`, `logout`, `auth status`, `config get|set` (url, theme, interval), shared preferences file. The session cookies are stored in the OS keyring (`SessionStore`) so the GUI and the CLI share one server-side session; without a keyring each side logs in on its own.
2. **Read commands** (done): `projects list|view`, `activities list`, `timesheets list|view|today`, with paging, `--all`, filters and relative dates.
3. **Log time** (done): `log add` (flags, prompts, `--recent`, `--duration`, `--at`, `--dry-run`) and `log list`.
4. **GUI tracker control** (done): single instance (`QLockFile`, stale locks from crashes are recovered), a loopback socket server (`src/ui/ipc_server.py`, protocol in `src/core/ipc.py`), tray icon (`src/ui/tray.py`), `--hidden`, close-to-tray while the tracker runs, `TrackerController` shared by the dashboard button, tray menu and socket.
5. **Tracker commands** (done): `start`, `stop`, `status`, `gui`, `remind` fallback, `data.refresh` after CLI saves.
6. **Parity, packaging and extras** (done): GUI/CLI parity test, shell completion, PyInstaller for both programs, and the change/delete commands `log edit`, `log rm`, `timesheets submit`, `timesheets rm` with matching GUI actions. Project create/edit is not possible with the account's server permissions.

## Open points
- Tray support varies on Linux. Some GNOME setups need an extension for tray icons. If the tray is unavailable, `--hidden` falls back to a minimized window.
- Console script is `samta-tracker`. It has no clash with GNOME's `tracker` search tool. A short alias (e.g. `st`) can be added later.

## Agent skill

`samta-tracker install-skill` copies `skills/samta-tracker/SKILL.md` (source; copied to `src/cli/skill/` by `scripts/sync_skill.py` and bundled with the app) to `~/.claude/skills/samta-tracker/`, so Claude Code and compatible agents can drive the CLI. Flags: `--project` (install into `./.claude/skills`), `--dir PATH` (another agent's skills folder), `--force` (overwrite a different copy; `-y` also works), `--print` (print instead of install). Re-running when identical is a no-op.
