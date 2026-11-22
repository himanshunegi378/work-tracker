---
name: samta-tracker
description: Control the Work Tracker (Samta/ERPNext timesheets) from the terminal with the `samta-tracker` CLI. Use when the user wants to log time, see or fix today's entries, list projects/activities/timesheets, check their leave applications or remaining leave balance, submit or delete a timesheet, or start/stop the desktop app's time-log reminder.
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

## Learn the user's mappings (read before every `log add`, update after)

The user does not want to repeat themselves. Keep what you learn in persistent memory
(your memory directory, one file per topic, indexed in `MEMORY.md`). Recall these files
**before** choosing a project, activity or billable value, and write to them whenever the
user answers a question or states a preference.

| Memory file | Contents |
|---|---|
| `samta-activity-mapping.md` | task wording/keywords → activity type (e.g. "code review, PR review" → Review) |
| `samta-project-mapping.md` | task wording/keywords/repos/clients → project id + name, plus the project's **billable** value |
| `samta-preferences.md` | everything else about how the user works with the tracker (see below) |

**Decision procedure for each entry**
1. **Activity**: infer from the task description, using the activity mapping first, then
   `activities list -s` to confirm the name is valid. If one match is clearly right, use it.
   If two or more are plausible or none fit, **ask the user** (offer the 2-4 best candidates),
   then save the keyword → activity rule.
2. **Project**: use the project mapping first. If the task text doesn't clearly point to one
   project (zero or several candidates from `projects list -s`), **ask**, then save the
   task keyword → project rule.
3. **Billable**: look up the project's billable value in the project mapping. If the project
   has none recorded, **ask "Is work on <project> billable?"** once, then save it against the
   project. Pass `--billable` / `--no-billable` explicitly to match it. Ask again only if the user
   says a specific entry is an exception (don't overwrite the project default for one-offs).
4. Batch the questions into a single ask when several are unknown. Never guess silently when in doubt.
5. When a mapping is used, say so in one short line in the dry-run preview
   ("Project: Crowst (saved mapping), Activity: Review, Billable: yes") so the user can correct it.
   If they correct you, **update the saved rule** rather than adding a conflicting one.

**Format for mapping files**: one rule per line, most specific first, with the date learned, e.g.
`- "code review", "PR", "review" -> Review (confirmed 2026-11-22)` and
`- crowst, crowst-api repo -> PRJ-0012 "Crowst" | billable: true (inferred 2026-11-22)`.
Use `confirmed` when the user answered or accepted the preview, `inferred` when you chose it yourself.
Merge into an existing rule instead of duplicating.

**Capture preferences in `samta-preferences.md`.** Whenever the user gives a task or instruction,
note anything durable it reveals, without waiting to be asked. Examples worth saving:
- how they phrase tasks and what they mean (shorthand, project nicknames, ticket-id formats)
- description style (terse vs detailed, tense, whether to include ticket ids)
- default scope of a request ("log" = today only? always past entries from the last entry?)
- default duration/rounding, working hours, lunch/break handling
- whether they want dry-run previews shown or applied straight away for routine entries
- when they want to be asked vs. just have it done (e.g. "don't ask me about submit on Fridays")
- recurring tasks (standup, meetings) and their usual project/activity/duration
Save only durable, repeatable preferences, not one-off details. Never store passwords or tokens.
The safety rules above (dry-run, `-y`, submit/delete confirmation) still apply
unless the user explicitly and durably relaxes one of them, in which case record exactly what they relaxed.

## Learn from corrections

Entries you created may be changed later, by you or by the user in the GUI. Treat every
change as feedback on your mapping.

- **At the start of any session that touches the tracker** (and before `log add`), run
  `--json log list` and compare today's entries (and yesterday's, if cheap) with what you
  logged earlier. If an entry you created now has a different activity, project or billable
  value, and the change was not made by you in this conversation, the user corrected you.
- When you spot a correction, **update the matching rule** in the mapping file (replace, don't
  append a conflicting one) and say so in one line: "Noted: 'PR review' now maps to Code Review, not Review."
- When the user asks you to `log edit` an activity/project/billable, treat that as a correction
  too: after applying it, update the rule the original choice came from.
- A correction on one entry is a hint, not a law. If the rule had several earlier confirmations,
  or the user said "just this once", record it as an exception note instead of replacing the rule.
- To tell your entries apart from the user's, note in the mapping line when a rule was
  "confirmed" (user answered or accepted a preview) vs "inferred" (you guessed). Inferred rules
  that survive uncorrected for a while may be promoted to confirmed; confirmed rules only change
  on explicit user feedback.

## Tidy the saved rules

Run this when the user says "review/clean up my saved rules", or on your own initiative once
a mapping file has grown past about 30 lines (then just offer it, don't do it silently).

1. Read all three memory files (`samta-activity-mapping.md`, `samta-project-mapping.md`,
   `samta-preferences.md`).
2. Find: duplicates and overlapping keywords, contradicting rules (newest confirmed one wins),
   rules pointing to an activity or project that no longer exists (check with
   `activities list` / `projects list --all`), projects now completed/cancelled/inactive,
   and one-off details that don't belong in preferences.
3. **Show the user a short proposed change list** (merge / drop / fix / ask), grouped by file.
   Don't rewrite anything until they approve; they can approve all or pick items.
4. Apply the approved changes, keep the "(confirmed)"/"(inferred)" and date tags, and end with
   a one-line summary ("merged 3, dropped 2, 1 left to decide").
5. Items you can't resolve (e.g. two plausible projects for a keyword) become questions for the user,
   not guesses.

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
| `leave list [--status open\|approved\|rejected\|cancelled] [--type NAME] [--from DATE] [--to DATE] [-n N] [--all]` | your leave applications, newest first. `--type` is the exact leave type name (e.g. `"Sick Leave"`, `"Privilege Leave"`; types are set per company). `--from`/`--to` match any leave overlapping the range. Read-only: applying for leave is not supported. |
| `leave balance [--date DATE]` | leaves allocated / taken / pending / remaining per leave type (only types with an allocation; Leave Without Pay has none) |
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
1. Recall saved mappings; otherwise `--json projects list -s crowst` → pick the id; `--json activities list -s review`. Ask + save if unclear (see "Learn the user's mappings").
2. `log add ... --duration 1h --billable|--no-billable --dry-run` → show the preview → run without `--dry-run`.
3. `--json log list` to confirm.

**"What did I do today?"** → `--json log list` and summarise (hours per project).

**"Fix my last entry"** → `--json log list`, `log edit last -d "..." --dry-run`, show diff, apply.

**"How many leaves do I have left?"** → `--json leave balance` and report `remaining_leaves` per type (mention any `leaves_pending_approval`).

**"How many leaves did I take this year?"** → `--json leave list --status approved --from 2026-01-01 --to 2026-12-31 --all`, then sum `total_leave_days` (group by `leave_type` if asked). Note a leave spanning the range edge counts in full.

**"Submit my timesheet"** → `timesheets today`, `timesheets submit NAME --dry-run`, show the user the total and wait for explicit confirmation, then `-y`.

## Troubleshooting
- `command not found`: the app/CLI isn't installed or not on PATH.
- Exit 3: not logged in. Exit 4: no display for GUI-control commands.
- "not found" (exit 2): wrong timesheet name or entry number; re-run `log list`.
- Edit refused: the timesheet is no longer Pending.
