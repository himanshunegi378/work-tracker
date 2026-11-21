# Work Tracker

A desktop app and a command line for logging time against a Frappe/ERPNext server
(default `https://matrix.samta.ai`). The two are **one application**: same login, same
data, same settings. Use whichever fits the moment, or let an AI agent drive the CLI.

- **Desktop app** (PySide6): dashboard, projects, activities, timesheets, a Smart Log prompt
  that reminds you to record time, light and dark themes, and a tray icon.
- **`samta-tracker` CLI**: everything the app does, scriptable. Also starts, stops and
  opens the desktop app.
- **Agent skill**: lets Claude Code and other agents use the CLI for you.

## Install

Requires Python 3.12.

```bash
git clone https://github.com/himanshunegi378/work-tracker.git
cd work-tracker
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
```

This installs two commands: `samta-tracker` (CLI) and `work-tracker-gui` (desktop app).
Standalone bundles can be built with PyInstaller, see [docs/packaging.md](docs/packaging.md).

### Debian / Ubuntu

Download `worktracker-ubuntu.deb` (from the `latest` GitHub Release or a workflow run) and install it. This
also puts `samta-tracker` on your PATH. Installing a newer `.deb` upgrades in place.

```bash
sudo apt install ./worktracker-ubuntu.deb
```

### Windows and macOS downloads

The downloadable zips are not installers, so `samta-tracker` is not on your PATH at first.
Either open the app and go to **Settings → Command line and AI agents → Install command-line
tool**, or run once from the unpacked folder:

```bash
./WorkTracker.app/Contents/MacOS/samta-tracker setup   # macOS
.\WorkTracker\samta-tracker.exe setup                   # Windows (PowerShell)
```

Then open a new terminal. `samta-tracker setup --undo` reverses it.

## Quick start

```bash
samta-tracker login            # or: samta-tracker login --ui   (credentials window)
samta-tracker status           # login, app, tracker, dashboard counts
samta-tracker log add -p "My Project" -a "Development" -d "Fixed the parser" --dry-run
samta-tracker log list         # today's entries, numbered
samta-tracker start --every 30m   # reminders in the desktop app (opens it in the tray)
```

Credentials are stored in your operating system's keyring and shared with the desktop
app, so logging in once covers both. Passwords are never written to disk by this project.

## Commands

| Area | Commands |
|---|---|
| Account | `login`, `logout`, `auth status` |
| Read | `projects list\|view`, `activities list`, `timesheets list\|view\|today`, `log list` |
| Record and change time | `log add`, `log edit`, `log rm` |
| Timesheets | `timesheets submit`, `timesheets rm` |
| Desktop app | `start`, `stop`, `status`, `gui`, `remind` |
| Settings | `config get\|set` (`url`, `theme`, `interval`) |
| Setup | `completion`, `install-skill` |

Global flags: `--json`, `-q/--quiet`, `-y/--yes`, `--no-color`. Exit codes: `0` ok, `1` error,
`2` usage, `3` not logged in, `4` desktop app unavailable.

Safety: only **Pending** timesheets can be edited, deleted or submitted. Changing commands
support `--dry-run` and ask for confirmation; without a terminal, destructive ones need `-y`.
Submitting cannot be undone from the app.

Full reference: [docs/cli-spec.md](docs/cli-spec.md).

## Use it from an AI agent

```bash
npx skills add himanshunegi378/work-tracker      # skills.sh installer, many agents (needs Node)

# no Node, or offline: copy the bundled skill instead
samta-tracker install-skill                      # Claude Code: ~/.claude/skills/samta-tracker
samta-tracker install-skill --dir <skills dir>   # another agent's skills folder
```

Then ask your agent things like "log 1h on <project> for code review" or "start the tracker".
The skill tells the agent to preview changes, never handle your password, and ask before
deleting or submitting. Source: [skills/samta-tracker/SKILL.md](skills/samta-tracker/SKILL.md).

## Development

```bash
pip install -e . pytest
python -m pytest tests -q
```

After editing the skill, run `python scripts/sync_skill.py` (a test checks the copies match).
Design notes: [docs/design-system.md](docs/design-system.md).

## License

No license has been chosen yet, so all rights are reserved by default. Add a `LICENSE` file
to allow others to use and modify the code.
