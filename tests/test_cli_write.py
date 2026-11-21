import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.services.timesheet_shared import TimesheetServiceError
from tests.test_cli_log import FakeActivities, FakeProjects

runner = CliRunner()
TODAY = date.today().isoformat()


def make_detail(state="Pending"):
    return {
        "name": "TS-9", "status": "Draft", "workflow_state": state, "start_date": TODAY, "end_date": TODAY,
        "total_hours": 3.0, "total_billable_hours": 0.0,
        "time_logs": [
            {"name": "abc1", "idx": 1, "activity_type": "Execution", "project": "PROJ-0007", "project_name": "TATVA",
             "description": "first", "from_time": f"{TODAY} 09:00:00", "to_time": f"{TODAY} 10:00:00",
             "hours": 1.0, "is_billable": 0},
            {"name": "abc2", "idx": 2, "activity_type": "Development", "project": "PROJ-0001", "project_name": "Billing",
             "description": "second", "from_time": f"{TODAY} 10:00:01", "to_time": f"{TODAY} 12:00:00",
             "hours": 2.0, "is_billable": 1},
        ],
    }


class FakeTimesheets:
    def __init__(self, state="Pending", actions=("Submit",)):
        self.detail = make_detail(state)
        self.actions = list(actions)
        self.calls = []
        self.fail = None

    def get_timesheets(self, **kw):
        return [{"name": "TS-9"}]

    def get_timesheet_detail(self, name, csrf_token=None):
        return self.detail

    def get_workflow_actions(self, name, csrf_token=None):
        return self.actions

    def _do(self, label, *args, **kwargs):
        if self.fail:
            raise TimesheetServiceError(self.fail)
        self.calls.append((label, args, kwargs))
        return {**self.detail, "workflow_state": "Submitted" if label == "submit" else self.detail["workflow_state"]}

    def update_time_log(self, ts, row, **changes):
        return self._do("update", ts, row, **changes)

    def delete_time_log(self, ts, row):
        return self._do("delete_row", ts, row)

    def submit_timesheet(self, name):
        return self._do("submit", name)

    def delete_timesheet(self, name):
        return self._do("delete", name)


@pytest.fixture
def env(monkeypatch):
    ts = FakeTimesheets()
    ctx = SimpleNamespace(projects=FakeProjects(), activities=FakeActivities(), timesheets=ts)
    for module in ("log", "timesheets"):
        monkeypatch.setattr(f"src.cli.commands.{module}.get_context", lambda c, base_url=None: ctx)
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: False)
    monkeypatch.setattr("src.cli.commands._common.is_interactive", lambda: False)
    return ts


@pytest.fixture
def tty(monkeypatch):
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: True)
    monkeypatch.setattr("src.cli.commands._common.is_interactive", lambda: True)


def run(*args, **kw):
    return runner.invoke(app, list(args), **kw)


# ── log edit ──────────────────────────────────────────────────────────────
def test_edit_maps_flags_to_service_changes(env):
    result = run("log", "edit", "2", "-d", "reworded", "-a", "Execution", "-p", "TATVA", "--billable")
    assert result.exit_code == 0, result.output
    label, args, changes = env.calls[0]
    assert (label, args) == ("update", ("TS-9", "abc2"))
    assert changes == {"description": "reworded", "activity": "Execution", "project_id": "PROJ-0007",
                       "project_name": "TATVA", "is_billable": True}
    assert "Updated entry #2 in TS-9" in result.output


def test_edit_times_are_attached_to_the_entrys_day(env):
    run("log", "edit", "1", "--to", "9:30", "--from", "9am")
    changes = env.calls[0][2]
    assert changes["from_time"] == datetime.fromisoformat(f"{TODAY} 09:00:00")
    assert changes["to_time"] == datetime.fromisoformat(f"{TODAY} 09:30:00")


def test_edit_last_and_internal_id(env):
    run("log", "edit", "last", "-d", "x")
    run("log", "edit", "abc1", "-d", "y")
    assert [c[1][1] for c in env.calls] == ["abc2", "abc1"]


def test_edit_needs_at_least_one_change_and_a_real_entry(env):
    assert run("log", "edit", "1").exit_code == 2
    result = run("log", "edit", "9", "-d", "x")
    assert result.exit_code == 2 and "entries 1 to 2" in result.output
    assert env.calls == []


@pytest.mark.parametrize("args", [["--from", "25:00"], ["--to", "9:00"], ["--from", "11:00"], ["-a", "Nope"], ["-p", "NOPE"]])
def test_edit_bad_values_never_reach_the_service(env, args):
    assert run("log", "edit", "1", *args).exit_code == 2
    assert env.calls == []


def test_edit_dry_run_shows_before_and_after_and_saves_nothing(env):
    result = run("log", "edit", "1", "-d", "reworded", "--to", "09:30", "--dry-run")
    assert result.exit_code == 0 and env.calls == []
    assert "first  →  reworded" in result.output and "09:00 → 10:00  →  09:00 → 09:30 (30m)" in result.output
    data = json.loads(run("--json", "log", "edit", "1", "-d", "z", "--dry-run").output)
    assert data["dry_run"] is True and data["changes"]["description"]["to"] == "z"


def test_edit_asks_in_a_terminal_and_can_be_declined(env, tty):
    assert run("log", "edit", "1", "-d", "x", input="n\n").exit_code == 1
    assert env.calls == []
    assert run("log", "edit", "1", "-d", "x", input="y\n").exit_code == 0
    assert len(env.calls) == 1
    assert run("-y", "log", "edit", "1", "-d", "x").exit_code == 0


def test_edit_surfaces_service_refusals(env):
    env.fail = "That overlaps another entry (10:00-12:00)."
    result = run("log", "edit", "1", "--to", "11:00")
    assert result.exit_code == 1 and "overlaps another entry" in result.output


def test_edit_picks_the_timesheet_by_name_or_date(env):
    assert run("log", "edit", "1", "-d", "x", "--timesheet", "TS-9").exit_code == 0
    assert run("log", "edit", "1", "-d", "x", "--date", "today").exit_code == 0
    assert run("log", "edit", "1", "-d", "x", "--date", "today", "--timesheet", "TS-9").exit_code == 2


# ── log rm ────────────────────────────────────────────────────────────────
def test_rm_requires_confirmation_or_yes_when_not_in_a_terminal(env):
    result = run("log", "rm", "1")
    assert result.exit_code == 2 and "pass -y" in result.output.lower() and env.calls == []


def test_rm_with_yes_deletes_the_entry(env):
    result = run("-y", "log", "rm", "2")
    assert result.exit_code == 0 and env.calls == [("delete_row", ("TS-9", "abc2"), {})]
    assert "Deleted entry #2 in TS-9" in result.output


def test_rm_dry_run_and_terminal_confirmation(env, tty):
    result = run("log", "rm", "1", "--dry-run")
    assert "Would delete entry #1" in result.output and env.calls == []
    assert run("log", "rm", "1", input="n\n").exit_code == 1 and env.calls == []
    assert run("log", "rm", "1", input="y\n").exit_code == 0 and len(env.calls) == 1


def test_rm_surfaces_the_only_entry_refusal(env):
    env.fail = "That is the only entry; delete the whole timesheet instead."
    result = run("-y", "log", "rm", "1")
    assert result.exit_code == 1 and "only entry" in result.output


# ── timesheets submit ─────────────────────────────────────────────────────
def test_submit_dry_run_reads_the_allowed_actions_and_submits_nothing(env):
    result = run("timesheets", "submit", "TS-9", "--dry-run")
    assert result.exit_code == 0 and "Action" in result.output and "Submit" in result.output and env.calls == []
    data = json.loads(run("--json", "timesheets", "submit", "TS-9", "--dry-run").output)
    assert data["available_actions"] == ["Submit"] and data["entries"] == 2


def test_submit_shows_when_the_action_is_not_available(env):
    env.actions = ["Approve"]
    assert "not available (Approve)" in run("timesheets", "submit", "TS-9", "--dry-run").output


def test_submit_never_runs_unattended_without_yes(env):
    result = run("timesheets", "submit", "TS-9")
    assert result.exit_code == 2 and env.calls == []


def test_submit_with_yes_and_in_a_terminal(env, tty):
    assert run("timesheets", "submit", "TS-9", input="n\n").exit_code == 1 and env.calls == []
    result = run("-y", "timesheets", "submit", "TS-9")
    assert result.exit_code == 0 and env.calls == [("submit", ("TS-9",), {})]
    assert "now Submitted" in result.output


def test_submit_refusal_from_the_service_is_reported(env):
    env.fail = "TS-9 is Submitted: only Pending drafts can be changed."
    result = run("-y", "timesheets", "submit", "TS-9")
    assert result.exit_code == 1 and "only Pending drafts" in result.output


# ── timesheets rm ─────────────────────────────────────────────────────────
def test_timesheets_rm_needs_yes_unattended_and_deletes_with_it(env):
    assert run("timesheets", "rm", "TS-9").exit_code == 2 and env.calls == []
    result = run("-y", "timesheets", "rm", "TS-9")
    assert result.exit_code == 0 and env.calls == [("delete", ("TS-9",), {})] and "Deleted TS-9" in result.output


def test_timesheets_rm_dry_run_and_decline(env, tty):
    assert "Dry run: nothing was deleted" in run("timesheets", "rm", "TS-9", "--dry-run").output
    assert run("timesheets", "rm", "TS-9", input="n\n").exit_code == 1 and env.calls == []


def test_timesheets_rm_json(env):
    data = json.loads(run("-y", "--json", "timesheets", "rm", "TS-9").output)
    assert data["deleted"] is True and data["entries"] == 2


# ── log list shows the numbers edit/rm use ────────────────────────────────
def test_log_list_has_a_number_column(env):
    result = run("log", "list")
    header = next(l for l in result.output.splitlines() if "ACTIVITY" in l).split()
    assert header[0] == "#" and "ACTIVITY" in header


def test_a_missing_timesheet_says_not_found(env):
    def missing(name, csrf_token=None):
        raise TimesheetServiceError("Malformed timesheet detail response: missing docs.")

    env.get_timesheet_detail = missing
    for args in (["timesheets", "rm", "TS-0"], ["timesheets", "submit", "TS-0"], ["timesheets", "view", "TS-0"],
                 ["log", "rm", "1", "--timesheet", "TS-0"]):
        result = run("-y", *args)
        assert result.exit_code == 2 and "was not found" in result.output, args
    assert env.calls == []
