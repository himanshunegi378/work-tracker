import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.core import prefs

runner = CliRunner()
TODAY = date.today().isoformat()

PROJECTS = [
    {"id": "PROJ-0001", "name": "Billing", "status": "Open"},
    {"id": "PROJ-0002", "name": "Billing Mobile", "status": "Open"},
    {"id": "PROJ-0007", "name": "TATVA", "status": "Open"},
]
ACTIVITIES = ["Development", "Development Review", "Execution", "Stand Up Call"]


class FakeProjects:
    def get_projects(self, search_text="", start=0, page_length=10, filters="{}", csrf_token=None):
        return [p for p in PROJECTS if search_text.lower() in (p["id"] + " " + p["name"]).lower()][:page_length]


class FakeActivities:
    def get_activity_names(self, search_text="", page_length=200, csrf_token=None):
        return [a for a in ACTIVITIES if search_text.lower() in a.lower()]


class FakeTimesheets:
    def __init__(self, previous=None, recent=None, detail=None):
        self.previous = previous
        self.recent = recent or []
        self.saved = []
        self.detail = detail or {"name": "TS-9", "time_logs": []}

    def get_latest_smart_log_state(self, **kw):
        return self.previous

    def get_recent_smart_log_options(self, limit=5, **kw):
        return self.recent

    def save_timesheet_log(self, **kwargs):
        self.saved.append(kwargs)
        end = kwargs["saved_at"]
        hours = kwargs["interval_seconds"] / 3600
        return {"name": "TS-9", "time_logs": [
            {"from_time": f"{end:%Y-%m-%d} 10:00:00", "to_time": f"{end:%Y-%m-%d} 12:00:00", "hours": hours}
        ]}

    def get_timesheets(self, **kw):
        return [{"name": "TS-9"}] if kw.get("covering_date") != "1999-01-01" else []

    def get_timesheet_detail(self, name, csrf_token=None):
        return self.detail


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")
    ts = FakeTimesheets()
    ctx = SimpleNamespace(projects=FakeProjects(), activities=FakeActivities(), timesheets=ts)
    monkeypatch.setattr("src.cli.commands.log.get_context", lambda c, base_url=None: ctx)
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: False)
    return ts


def run(*args, **kw):
    return runner.invoke(app, list(args), **kw)


BASE = ["log", "add", "-p", "TATVA", "-a", "Execution", "-d", "Wrote tests"]


# ── saving ────────────────────────────────────────────────────────────────
def test_add_saves_with_resolved_names_and_confirms(env):
    result = run(*BASE, "--duration", "1h")
    assert result.exit_code == 0, result.output
    saved = env.saved[0]
    assert (saved["project_id"], saved["project_name"], saved["activity"]) == ("PROJ-0007", "TATVA", "Execution")
    assert saved["description"] == "Wrote tests" and saved["is_billable"] is False
    assert saved["interval_seconds"] == 3600 and isinstance(saved["saved_at"], datetime)
    assert "Logged 1h on PROJ-0007 / Execution in TS-9" in result.output


def test_add_without_duration_uses_the_configured_interval(env):
    prefs.set_value("interval", "20m")
    run(*BASE)
    assert env.saved[0]["interval_seconds"] == 1200


def test_add_matches_names_case_insensitively_and_by_id(env):
    run("log", "add", "-p", "proj-0007", "-a", "execution", "-d", "x")
    assert env.saved[0]["project_name"] == "TATVA" and env.saved[0]["activity"] == "Execution"


def test_add_billable_flags(env):
    run(*BASE, "--billable")
    assert env.saved[-1]["is_billable"] is True
    run(*BASE, "--no-billable")
    assert env.saved[-1]["is_billable"] is False


def test_billable_defaults_to_the_last_entry_for_the_same_project_and_activity(env):
    env.previous = {"timesheet_name": "T", "project_id": "PROJ-0007", "activity_name": "Execution",
                    "description": "old", "is_billable": True, "timestamp": "2020-01-01 10:00:00"}
    run(*BASE)
    assert env.saved[0]["is_billable"] is True


def test_add_json_output(env):
    out = json.loads(run("--json", *BASE, "--duration", "30m").output)
    assert out["saved"] is True and out["timesheet"] == "TS-9" and out["project_id"] == "PROJ-0007"
    assert out["hours"] == 0.5 and out["extends_previous"] is False


# ── dry run ───────────────────────────────────────────────────────────────
def test_dry_run_saves_nothing_and_shows_the_plan(env):
    result = run(*BASE, "--duration", "45m", "--dry-run")
    assert result.exit_code == 0 and env.saved == []
    assert "Dry run: nothing was saved" in result.output and "45m" in result.output and "TATVA" in result.output


def test_dry_run_json(env):
    out = json.loads(run("--json", *BASE, "--duration", "45m", "--dry-run").output)
    assert out["dry_run"] is True and out["hours"] == 0.75 and env.saved == []


# ── backdating ────────────────────────────────────────────────────────────
def test_past_day_with_at_and_duration(env):
    result = run(*BASE, "--date", "2026-10-28", "--at", "18:00", "--duration", "2h")
    assert result.exit_code == 0
    saved = env.saved[0]
    assert saved["saved_at"] == datetime(2026, 10, 28, 18, 0) and saved["interval_seconds"] == 7200


def test_past_day_requires_at_and_duration(env):
    assert run(*BASE, "--date", "2026-10-28").exit_code == 2
    assert run(*BASE, "--date", "2026-10-28", "--at", "18:00").exit_code == 2
    assert env.saved == []


def test_at_requires_duration_and_future_is_rejected(env):
    assert run(*BASE, "--at", "09:00").exit_code == 2
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    result = run(*BASE, "--date", tomorrow, "--at", "09:00", "--duration", "1h")
    assert result.exit_code == 2 and "future" in result.output and env.saved == []


# ── validation ────────────────────────────────────────────────────────────
def test_unknown_project_and_activity(env):
    assert run("log", "add", "-p", "NOPE", "-a", "Execution", "-d", "x").exit_code == 2
    result = run("log", "add", "-p", "TATVA", "-a", "Nope", "-d", "x")
    assert result.exit_code == 2 and "activities list" in result.output and env.saved == []


def test_ambiguous_project_lists_candidates(env):
    result = run("log", "add", "-p", "Bill", "-a", "Execution", "-d", "x")
    assert result.exit_code == 2
    assert "PROJ-0001" in result.output and "PROJ-0002" in result.output and env.saved == []


def test_ambiguous_activity_lists_candidates(env):
    result = run("log", "add", "-p", "TATVA", "-a", "Development", "-d", "x")
    assert result.exit_code == 0  # exact match wins over "Development Review"
    result = run("log", "add", "-p", "TATVA", "-a", "Dev", "-d", "x")
    assert result.exit_code == 2 and "Development Review" in result.output


def test_missing_fields_without_a_terminal_are_usage_errors(env):
    assert run("log", "add", "-a", "Execution", "-d", "x").exit_code == 2
    assert run("log", "add", "-p", "TATVA", "-d", "x").exit_code == 2
    result = run("log", "add", "-p", "TATVA", "-a", "Execution")
    assert result.exit_code == 2 and "Pass -d" in result.output


@pytest.mark.parametrize("duration", ["abc", "0m", "30s", "30h"])
def test_bad_duration(env, duration):
    assert run(*BASE, "--duration", duration).exit_code == 2
    assert env.saved == []


def test_merge_is_announced(env):
    env.previous = {"timesheet_name": "TS-9", "project_id": "PROJ-0007", "activity_name": "Execution",
                    "description": "Wrote tests", "is_billable": False,
                    "timestamp": f"{TODAY} 00:01:00"}
    result = run(*BASE, "--duration", "10m", "--dry-run")
    assert "extends your previous entry" in result.output


# ── interactive behaviour ─────────────────────────────────────────────────
@pytest.fixture
def tty(monkeypatch):
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: True)


def test_prompts_for_missing_values_then_confirms(env, tty):
    result = run("log", "add", input="TATVA\nExecution\nDid things\nn\ny\n")  # project, activity, desc, billable, save
    assert result.exit_code == 0, result.output
    assert env.saved[0]["description"] == "Did things" and env.saved[0]["is_billable"] is False


def test_declining_the_confirmation_saves_nothing(env, tty):
    result = run(*BASE, "--no-billable", input="n\n")
    assert result.exit_code == 1 and "Nothing saved" in result.output and env.saved == []


def test_yes_flag_skips_the_confirmation(env, tty):
    result = run("-y", *BASE, "--no-billable")
    assert result.exit_code == 0 and len(env.saved) == 1


def test_recent_fills_project_activity_and_billable(env, tty):
    env.recent = [
        {"project_id": "PROJ-0001", "project_name": "Billing", "activity_name": "Development",
         "is_billable": True, "description": "old text"},
        {"project_id": "PROJ-0007", "project_name": "TATVA", "activity_name": "Execution",
         "is_billable": False, "description": ""},
    ]
    result = run("-y", "log", "add", "--recent", "-d", "New work", input="1\n")
    assert result.exit_code == 0, result.output
    saved = env.saved[0]
    assert (saved["project_id"], saved["activity"], saved["is_billable"]) == ("PROJ-0001", "Development", True)


def test_recent_needs_a_terminal(env):
    assert run("log", "add", "--recent").exit_code == 2


# ── log list ──────────────────────────────────────────────────────────────
def _detail():
    return {"name": "TS-9", "time_logs": [
        {"name": "r1", "activity_type": "Execution", "project": "PROJ-0007", "project_name": "TATVA",
         "description": "morning", "from_time": f"{TODAY} 09:00:00", "to_time": f"{TODAY} 10:30:00", "hours": 1.5, "is_billable": 0},
        {"name": "r2", "activity_type": "Review", "project": "PROJ-0001", "project_name": "Billing",
         "description": "other day", "from_time": "2020-01-01 09:00:00", "to_time": "2020-01-01 10:00:00", "hours": 1.0, "is_billable": 1},
    ]}


def test_list_today_shows_only_todays_entries_with_total(env):
    env.detail = _detail()
    result = run("log", "list")
    assert "morning" in result.output and "other day" not in result.output
    assert "1 entry · 1h30m total" in result.output


def test_list_for_a_whole_timesheet_and_json(env):
    env.detail = _detail()
    assert "other day" in run("log", "list", "--timesheet", "TS-9").output
    assert len(json.loads(run("--json", "log", "list", "--timesheet", "TS-9").output)) == 2


def test_list_nothing_found(env):
    env.detail = _detail()
    assert "No entries for 1999-01-01" in run("log", "list", "--date", "1999-01-01").output
    assert json.loads(run("--json", "log", "list", "--date", "1999-01-01").output) == []


def test_list_rejects_conflicting_or_bad_options(env):
    assert run("log", "list", "--date", "today", "--timesheet", "TS-9").exit_code == 2
    assert run("log", "list", "--date", "whenever").exit_code == 2


def test_recent_reprompts_on_an_out_of_range_choice(env, tty):
    env.recent = [{"project_id": "PROJ-0007", "project_name": "TATVA", "activity_name": "Execution",
                   "is_billable": False, "description": ""}]
    result = run("-y", "log", "add", "--recent", "-d", "x", input="9\n1\n")
    assert result.exit_code == 0 and "from 1 to 1" in result.output
    assert env.saved[0]["project_id"] == "PROJ-0007"


def test_list_json_keeps_raw_values_while_the_table_is_tidied(env):
    env.detail = {"name": "TS-9", "time_logs": [
        {"name": "r1", "activity_type": "Execution", "project": "P", "project_name": "TATVA", "description": "d",
         "from_time": f"{TODAY} 09:00:05", "to_time": f"{TODAY} 10:30:10", "hours": 1.5028, "is_billable": 1}]}
    raw = json.loads(run("--json", "log", "list").output)[0]
    assert raw["from_time"] == f"{TODAY} 09:00:05" and raw["hours"] == 1.5028 and raw["is_billable"] == 1
    table = run("log", "list").output
    assert f"{TODAY} 09:00" in table and "09:00:05" not in table


def test_total_uses_the_exact_timesheet_total_for_a_one_day_timesheet(env):
    env.detail = {"name": "TS-9", "start_date": TODAY, "end_date": TODAY, "total_hours": 0.099722, "time_logs": [
        {"name": "r1", "activity_type": "E", "project": "P", "project_name": "T", "description": "d",
         "from_time": f"{TODAY} 19:34:00", "to_time": f"{TODAY} 19:40:00", "hours": 0.1, "is_billable": 0}]}
    assert "5m59s total" in run("log", "list").output
