import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()

PROJECTS = [
    {"id": f"PROJ-{i:04d}", "name": f"Proj{i}", "description": None,
     "status": "Open" if i % 2 else "Completed", "priority": "Medium", "is_active": i % 3 != 0}
    for i in range(1, 31)
]


class FakeProjects:
    def __init__(self, data=PROJECTS):
        self.data = data
        self.calls = []

    def get_projects(self, search_text="", start=0, page_length=10, filters="{}", csrf_token=None):
        self.calls.append({"search": search_text, "start": start, "n": page_length, "filters": json.loads(filters)})
        rows = [p for p in self.data if search_text.lower() in (p["id"] + p["name"]).lower()]
        return rows[start:start + page_length]


class FakeActivities:
    def get_activities(self, search_text="", start=0, page_length=10, csrf_token=None):
        names = [{"name": n} for n in ("Development", "Review", "Stand Up Call")]
        return [a for a in names if search_text.lower() in a["name"].lower()][start:start + page_length]


DETAIL = {
    "name": "TS-1", "status": "Draft", "workflow_state": "Pending", "employee_name": "Jane Doe",
    "department": "Tech", "company": "Acme", "currency": "INR", "start_date": "2026-10-26",
    "end_date": "2026-10-28", "total_hours": 12.5, "total_billable_hours": 4.0, "total_billable_amount": 100.0,
    "time_logs": [
        {"activity_type": "Development", "project": "PROJ-1", "project_name": "Proj1", "description": "Fix bug",
         "from_time": "2026-10-27 09:00:00", "to_time": "2026-10-27 12:30:00", "hours": 3.5, "is_billable": 1},
        {"activity_type": "Review", "project": "PROJ-2", "project_name": "", "description": "PR review",
         "from_time": "2026-10-28 10:00:00", "to_time": "2026-10-28 11:00:00", "hours": 1.0, "is_billable": 0},
        {"activity_type": "Review", "project": "PROJ-2", "project_name": "Proj2", "description": "More review",
         "from_time": "2026-10-28 14:00:00", "to_time": "2026-10-28 15:30:00", "hours": 1.5, "is_billable": 0},
    ],
}


class FakeTimesheets:
    def __init__(self, rows=None, covering=True):
        self.rows = rows if rows is not None else [
            {"name": "TS-1", "status": "Draft", "workflow_state": "Pending",
             "start_date": "2026-10-26", "end_date": "2026-10-28", "total_hours": 12.5}
        ]
        self.covering = covering
        self.calls = []

    def get_timesheets(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("covering_date") and not self.covering:
            return []
        return self.rows[kwargs.get("start", 0):][: kwargs.get("page_length", 20)]

    def get_timesheet_detail(self, name, csrf_token=None):
        return DETAIL


@pytest.fixture
def projects(monkeypatch):
    fake = FakeProjects()
    monkeypatch.setattr("src.cli.commands.projects.get_context", lambda c, base_url=None: SimpleNamespace(projects=fake))
    return fake


@pytest.fixture
def timesheets(monkeypatch):
    fake = FakeTimesheets()
    monkeypatch.setattr("src.cli.commands.timesheets.get_context", lambda c, base_url=None: SimpleNamespace(timesheets=fake))
    return fake


def run(*args, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


# ── projects list ─────────────────────────────────────────────────────────
def test_projects_list_default_table(projects):
    result = run("projects", "list")
    assert result.exit_code == 0
    assert "ID" in result.output and "PROJ-0001" in result.output
    assert projects.calls[0]["n"] == 20 and projects.calls[0]["start"] == 0
    assert "more may exist (--page 2)" in result.output


def test_projects_list_limit_and_page_map_to_offset(projects):
    run("projects", "list", "-n", "5", "--page", "3")
    assert (projects.calls[0]["start"], projects.calls[0]["n"]) == (10, 5)


def test_projects_list_status_priority_and_search_are_sent_to_server(projects):
    run("projects", "list", "--status", "open", "--priority", "high", "-s", "Proj1")
    call = projects.calls[0]
    assert call["filters"] == {"status": "Open", "priority": "High"}
    assert call["search"] == "Proj1"


def test_projects_list_active_filter(projects):
    out = json.loads(run("--json", "projects", "list", "--inactive", "-n", "30").output)
    assert out and all(p["is_active"] is False for p in out)
    out = json.loads(run("--json", "projects", "list", "--active", "-n", "30").output)
    assert out and all(p["is_active"] for p in out)


def test_projects_list_json_and_quiet(projects):
    data = json.loads(run("--json", "projects", "list", "-n", "2").output)
    assert [p["id"] for p in data] == ["PROJ-0001", "PROJ-0002"]
    assert run("-q", "projects", "list", "-n", "2").output.split() == ["PROJ-0001", "PROJ-0002"]


def test_projects_list_empty(projects):
    result = run("projects", "list", "-s", "zzz")
    assert result.exit_code == 0 and "No projects found." in result.output
    assert json.loads(run("--json", "projects", "list", "-s", "zzz").output) == []


def test_projects_list_all_is_capped_at_250_and_chunked(monkeypatch):
    many = [{"id": f"P{i}", "name": f"n{i}", "description": None, "status": "Open", "priority": "Low", "is_active": True}
            for i in range(600)]
    fake = FakeProjects(many)
    monkeypatch.setattr("src.cli.commands.projects.get_context", lambda c, base_url=None: SimpleNamespace(projects=fake))
    out = json.loads(run("--json", "projects", "list", "--all").output)
    assert len(out) == 250
    assert [c["n"] for c in fake.calls] == [100, 100, 50]
    out = json.loads(run("--json", "projects", "list", "--all", "-n", "400").output)
    assert len(out) == 400


def test_projects_list_bad_flags_are_usage_errors(projects):
    assert run("projects", "list", "--all", "--page", "2").exit_code == 2
    assert run("projects", "list", "--status", "banana").exit_code == 2
    assert run("projects", "list", "-n", "0").exit_code == 2
    assert run("projects", "list", "-n", "5000").exit_code == 2
    assert run("projects", "list", "--page", "0").exit_code == 2


# ── projects view ─────────────────────────────────────────────────────────
def test_projects_view_found_by_id_or_name(projects):
    result = run("projects", "view", "proj-0002")
    assert result.exit_code == 0 and "PROJ-0002" in result.output and "Proj2" in result.output
    assert run("projects", "view", "Proj2").exit_code == 0


def test_projects_view_not_found_exits_1(projects):
    result = run("projects", "view", "NOPE")
    assert result.exit_code == 1 and "not found" in result.output


def test_projects_view_json(projects):
    assert json.loads(run("--json", "projects", "view", "PROJ-0001").output)["id"] == "PROJ-0001"


# ── activities ────────────────────────────────────────────────────────────
def test_activities_list(monkeypatch):
    monkeypatch.setattr("src.cli.commands.activities.get_context", lambda c, base_url=None: SimpleNamespace(activities=FakeActivities()))
    result = run("activities", "list")
    assert "Development" in result.output and "Stand Up Call" in result.output
    assert run("-q", "activities", "list", "-s", "rev").output.split() == ["Review"]
    assert json.loads(run("--json", "activities", "list", "-s", "dev").output) == [{"name": "Development"}]


# ── timesheets list ───────────────────────────────────────────────────────
def test_timesheets_list_table_and_filters(timesheets):
    result = run("timesheets", "list", "--status", "submitted", "--workflow-state", "Approved",
                 "--from", "2026-10-01", "--to", "2026-10-31", "--employee", "x@y.z", "-n", "5", "--page", "2")
    assert result.exit_code == 0
    call = timesheets.calls[0]
    assert call["status"] == "Submitted" and call["workflow_state"] == "Approved"
    assert str(call["from_date"]) == "2026-10-01" and str(call["to_date"]) == "2026-10-31"
    assert call["employee"] == "x@y.z" and (call["start"], call["page_length"]) == (5, 5)


def test_timesheets_list_output(timesheets):
    result = run("timesheets", "list")
    assert "NAME" in result.output and "WORKFLOW" in result.output and "TS-1" in result.output
    assert json.loads(run("--json", "timesheets", "list").output)[0]["name"] == "TS-1"
    assert run("-q", "timesheets", "list").output.split() == ["TS-1"]


def test_timesheets_list_relative_dates(timesheets):
    from datetime import date, timedelta

    run("timesheets", "list", "--from", "-7d", "--to", "today")
    call = timesheets.calls[0]
    assert call["from_date"] == date.today() - timedelta(days=7) and call["to_date"] == date.today()


def test_timesheets_list_bad_dates(timesheets):
    assert run("timesheets", "list", "--from", "soon").exit_code == 2
    result = run("timesheets", "list", "--from", "2026-11-02", "--to", "2026-11-01")
    assert result.exit_code == 2 and "--from is after --to" in result.output
    assert run("timesheets", "list", "--status", "banana").exit_code == 2


# ── timesheets view ───────────────────────────────────────────────────────
def test_timesheets_view_shows_logs_by_default(timesheets):
    result = run("timesheets", "view", "TS-1")
    assert result.exit_code == 0
    assert "Jane Doe" in result.output and "2026-10-26 → 2026-10-28" in result.output and "100.0 INR" in result.output
    assert "ACTIVITY" in result.output and "Fix bug" in result.output
    assert "2026-10-27 09:00" in result.output and "09:00:00" not in result.output  # minutes precision
    assert "PROJ-2" in result.output  # falls back to the id when project_name is blank


def test_timesheets_view_no_logs(timesheets):
    result = run("timesheets", "view", "TS-1", "--no-logs")
    assert "Jane Doe" in result.output and "ACTIVITY" not in result.output


def test_timesheets_view_json_has_full_detail(timesheets):
    data = json.loads(run("--json", "timesheets", "view", "TS-1").output)
    assert len(data["time_logs"]) == 3


# ── timesheets today ──────────────────────────────────────────────────────
def test_today_uses_covering_date_and_shows_only_that_days_logs(timesheets):
    result = run("timesheets", "today", "--date", "2026-10-28")
    assert result.exit_code == 0
    assert timesheets.calls[0]["covering_date"] == "2026-10-28"
    assert "Logged on 2026-10-28" in result.output and "2.5 h" in result.output
    assert "PR review" in result.output and "More review" in result.output
    assert "Fix bug" not in result.output  # logged on a different day


def test_today_no_logs_flag_and_json(timesheets):
    assert "ACTIVITY" not in run("timesheets", "today", "--date", "2026-10-28", "--no-logs").output
    data = json.loads(run("--json", "timesheets", "today", "--date", "2026-10-28").output)
    assert data["date"] == "2026-10-28" and data["hours_on_date"] == 2.5 and data["timesheet"]["name"] == "TS-1"


def test_today_when_nothing_covers_the_day_exits_1(monkeypatch):
    fake = FakeTimesheets(covering=False)
    monkeypatch.setattr("src.cli.commands.timesheets.get_context", lambda c, base_url=None: SimpleNamespace(timesheets=fake))
    result = run("timesheets", "today")
    assert result.exit_code == 1 and "No timesheet covers" in result.output


def test_today_defaults_to_the_real_today(timesheets):
    from datetime import date

    run("timesheets", "today")
    assert timesheets.calls[0]["covering_date"] == date.today().isoformat()


def test_today_rejects_bad_date(timesheets):
    assert run("timesheets", "today", "--date", "whenever").exit_code == 2
