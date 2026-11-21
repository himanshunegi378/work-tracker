---
name: samta-tracker
description: Control the Work Tracker (Samta/ERPNext timesheets) from the terminal with the `samta-tracker` CLI. Use when the user wants to log time, see or fix today's entries, list projects/activities/timesheets, submit or delete a timesheet, or start/stop the desktop app's time-log reminder.
---

# samta-tracker

`samta-tracker` is the command line of the Work Tracker desktop app. It is the
same app as the GUI: same login, same data, same settings. Requires the app to
be installed (this puts `samta-tracker` on PATH).

## Ground rules for agents

1. **Always pass `--json`** (global flag, goes before the command) when you need to read output:
   `samta-tracker --json log list`. Never scrape the pretty tables.
2. **Never prompt-block.** You have no terminal: destructive commands (`log rm`,
   `timesheets rm`, `timesheets submit`) refuse to run without `-y`. Always run
   `--dry-run` first, show the user the preview, get their OK, then repeat with `-y`.
3. **Ask before irreversible actions.** `timesheets submit` cannot be undone by the user.
   Deleting is permanent. Never run these without the user's explicit go-ahead in this conversation.
4. **Never ask for or handle the user's password.** If not logged in (exit code 3), tell the
   user to run `samta-tracker login --ui` (opens a window) or `samta-tracker login` themselves.
5. Only timesheets in the **Pending** workflow state can be edited, deleted or submitted.
   Submitted/approved ones are refused with a reason; report it, don't work around it.
6. Check the exit code: `0` ok, `1` error, `2` bad usage/not found, `3` not logged in,
   `4` desktop app unavailable (no display / failed to start).

## First steps

```
samta-tracker --json status      # login, app running?, tracker running?, dashboard counts
```
Exit 3 → user must log in (rule 4). Exit 4 on `start`/`gui` → no display; use `remind` only if a terminal is attached, otherwise tell the user.

## Command reference

Global flags (before the command): `--json`, `--no-color`, `-q/--quiet` (ids only), `-y/--yes`.

### Read
| Command | Notes |
|---|---|
| `status` | login, app, tracker, counts |
| `projects list [-s TEXT] [--status open\|completed\|cancelled] [--priority high\|medium\|low] [--active\|--inactive] [-n N] [--page P] [--all]` | find the project id/name for logging |
| `projects view ID` | one project |
| `activities list [-s TEXT] [-n N] [--all]` | valid activity types |
| `timesheets list [--status draft\|submitted\|...] [--workflow-state STATE] [--from DATE] [--to DATE] [-n N] [--all]` | newest first |
| `timesheets view NAME` / `timesheets today` | a timesheet with its entries |
| `log list [--date DATE] [--timesheet NAME]` | entries with a `#` column used by edit/rm |

Dates accept `YYYY-MM-DD`, `today`, `yesterday`, `-7d`, `-2w`, or a weekday name. Times accept `14:30`, `2:30pm`, `now`. Durations: `45m`, `1h30m`.

### Record and change time (Pending timesheets only)
```
samta-tracker --json log add -p "<project id or name>" -a "<activity>" -d "<what was done>" --duration 45m --dry-run
samta-tracker --json log add -p ... -a ... -d ... --duration 45m          # after the user agrees
samta-tracker --json log add ... --date yesterday --at 17:30 --duration 2h   # past day needs --at and --duration
samta-tracker --json log edit 2 -d "new text" [-a ACT] [-p PROJ] [--billable|--no-billable] [--from T] [--to T] --dry-run
samta-tracker --json log rm 2 --dry-run          # then add -y once approved
```
- Without `--duration`, `log add` fills the time since the user's previous entry. Always `--dry-run` first and tell the user the resulting start/end/hours.
- Entry selector is the `#` from `log list` (or `last`). Overlapping entries and bad times are refused.
- Look up `-p` and `-a` with `projects list -s` / `activities list -s` instead of guessing. Do not use `--recent` (interactive).

### Timesheets
```
samta-tracker --json timesheets submit TS-2026-00418 --dry-run   # checks it can be submitted
samta-tracker timesheets submit TS-2026-00418 -y                 # ONLY after explicit user approval
samta-tracker timesheets rm TS-2026-00418 --dry-run              # then -y after approval
```

### Reminder tracker (controls the desktop app)
```
samta-tracker start [--every 15m] [--show]   # launches the app in the tray if needed, starts reminders
samta-tracker stop [--quit]                  # stop reminders; --quit also closes the app
samta-tracker gui                            # open/raise the window
```
Needs a graphical session (exit 4 otherwise). `start` pops the Smart Log prompt on the user's screen immediately.

### Settings
`samta-tracker config get [url|theme|interval]`, `config set theme dark`, `config set interval 30m`.

## Typical workflows

**"Log 1h on Crowst for code review"**
1. `--json projects list -s crowst` → pick the id; `--json activities list -s review`.
2. `log add ... --duration 1h --dry-run` → show the preview → run without `--dry-run`.
3. `--json log list` to confirm.

**"What did I do today?"** → `--json log list` and summarise (hours per project).

**"Fix my last entry"** → `--json log list`, `log edit last -d "..." --dry-run`, show diff, apply.

**"Submit my timesheet"** → `timesheets today`, `timesheets submit NAME --dry-run`, show the user the total and wait for explicit confirmation, then `-y`.

## Troubleshooting
- `command not found`: the app/CLI isn't installed or not on PATH.
- Exit 3: not logged in. Exit 4: no display for GUI-control commands.
- "not found" (exit 2): wrong timesheet name or entry number; re-run `log list`.
- Edit refused: the timesheet is no longer Pending.
