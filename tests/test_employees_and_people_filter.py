import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.services.employee_service import EmployeeService, EmployeeServiceError
from src.services.timesheet_service import TimesheetService
from src.services.timesheet_shared import TimesheetAuthError

runner = CliRunner()
PEOPLE = [{"employee": "a@x.ai", "employee_name": "Ankush"}, {"employee": "IN00133", "employee_name": "Shrey Bhatt"}]


def run(*args):
    return runner.invoke(app, list(args))


# ── EmployeeService ───────────────────────────────────────────────────────
def make_employees(session="me@x.ai"):
    api = MagicMock()
    api.get_cookies.return_value = {}
    auth = MagicMock()
    auth.getSession.return_value = session
    return EmployeeService(api, auth), api


def test_employees_sorted_cleaned_and_self_optional():
    service, api = make_employees()
    api.get.return_value.json.return_value = {"message": [
        {"name": "z@x.ai", "employee_name": "Zed  Last"}, {"name": "me@x.ai", "employee_name": "Me Myself"},
        {"name": "IN1", "employee_name": "Amy"}, {"name": "", "employee_name": "bad"}]}
    assert [p["employee"] for p in service.get_employees()] == ["IN1", "me@x.ai", "z@x.ai"]
    people = service.get_employees(include_self=False)
    assert [p["employee"] for p in people] == ["IN1", "z@x.ai"]
    assert people[1]["employee_name"] == "Zed Last"
    assert api.get.call_args.kwargs["params"]["doctype"] == "Employee"


def test_employees_api_failure_becomes_service_error():
    from src.api import ApiClientError
    service, api = make_employees()
    api.get.side_effect = ApiClientError("boom")
    with pytest.raises(EmployeeServiceError):
        service.get_employees()


def test_cli_employees(monkeypatch):
    fake = SimpleNamespace(get_employees=lambda **k: PEOPLE)
    monkeypatch.setattr("src.cli.commands.employees.get_context", lambda c, base_url=None: SimpleNamespace(employees=fake))
    out = run("employees").output
    assert "IN00133" in out and "Shrey Bhatt" in out
    assert run("-q", "employees").output.split() == ["a@x.ai", "IN00133"]
    assert json.loads(run("--json", "employees").output)[0]["employee_name"] == "Ankush"


# ── TimesheetService ──────────────────────────────────────────────────────
def make_timesheets(session="me@x.ai"):
    api = MagicMock()
    api.get_cookies.return_value = {}
    api.post.return_value.json.return_value = {"message": {"keys": ["name", "employee_name"], "values": []}}
    auth = MagicMock()
    auth.getSession.return_value = session
    return TimesheetService(api, auth), api


def sent_filters(api):
    return json.loads(parse_qs(api.post.call_args.kwargs["data"])["filters"][0])


def test_timesheets_default_is_me_and_asks_for_the_employee_columns():
    service, api = make_timesheets()
    service.get_timesheets()
    assert sent_filters(api) == [["Timesheet", "employee", "=", "me@x.ai"]]
    fields = json.loads(parse_qs(api.post.call_args.kwargs["data"])["fields"][0])
    assert "`tabTimesheet`.`employee`" in fields and "`tabTimesheet`.`employee_name`" in fields


def test_timesheet_employee_names_are_tidied():
    service, api = make_timesheets()
    api.post.return_value.json.return_value = {"message": {"keys": ["name", "employee_name"], "values": [["T1", "Shrey  Bhatt"]]}}
    assert service.get_timesheets()[0]["employee_name"] == "Shrey Bhatt"


def test_timesheets_all_employees_drops_the_employee_filter():
    service, api = make_timesheets()
    service.get_timesheets(all_employees=True, status="Draft")
    assert sent_filters(api) == [["Timesheet", "status", "=", "Draft"]]
    service.get_timesheets(all_employees=True, employee="a@x.ai")  # an explicit person wins
    assert sent_filters(api) == [["Timesheet", "employee", "=", "a@x.ai"]]


def test_timesheets_all_employees_needs_no_login_but_default_does():
    service, _ = make_timesheets(session=None)
    service.get_timesheets(all_employees=True)
    with pytest.raises(TimesheetAuthError):
        service.get_timesheets()


# ── CLI: timesheets list ──────────────────────────────────────────────────
class FakeTimesheets:
    def __init__(self):
        self.calls = []

    def get_timesheets(self, **kwargs):
        self.calls.append(kwargs)
        return [{"name": "TS-1", "employee_name": "Ankush", "status": "Draft", "workflow_state": "Pending",
                 "start_date": "2026-11-16", "end_date": "2026-11-22", "total_hours": 10.0}]


@pytest.fixture
def timesheets(monkeypatch):
    fake = FakeTimesheets()
    monkeypatch.setattr("src.cli.commands.timesheets.get_context", lambda c, base_url=None: SimpleNamespace(timesheets=fake))
    return fake


def test_cli_timesheets_default_has_no_employee_column(timesheets):
    out = run("timesheets", "list").output
    assert "TS-1" in out and "EMPLOYEE" not in out
    assert timesheets.calls[0]["all_employees"] is False


def test_cli_timesheets_all_employees_adds_the_column(timesheets):
    out = run("timesheets", "list", "--all-employees").output
    assert "EMPLOYEE" in out and "Ankush" in out
    assert timesheets.calls[0]["all_employees"] is True
    assert "EMPLOYEE" in run("timesheets", "list", "--employee", "a@x.ai").output


def test_cli_timesheets_all_employees_conflicts_with_employee(timesheets):
    result = run("timesheets", "list", "--all-employees", "--employee", "a@x.ai")
    assert result.exit_code != 0 and not timesheets.calls


# ── GUI: timesheet list dropdown, detail read-only ────────────────────────
@pytest.fixture
def ts_page(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from src.ui import timesheet_list_presenter as mod
    from src.ui.views.timesheet_list_view import TimesheetListView

    QApplication.instance() or QApplication([])

    class Inline:  # run workers immediately instead of on the thread pool
        @staticmethod
        def globalInstance():
            return SimpleNamespace(start=lambda worker: worker.run())

    monkeypatch.setattr(mod, "QThreadPool", Inline)
    service = MagicMock()
    service.get_timesheets.return_value = [
        {"name": "TS-1", "employee_name": "Ankush", "workflow_state": "Pending", "status": "Draft",
         "start_date": "2026-11-16", "end_date": "2026-11-22", "total_hours": 10}]
    employees = MagicMock()
    employees.get_employees.return_value = [PEOPLE[0]]
    view = TimesheetListView()
    presenter = mod.TimesheetListPresenter(view, service, employee_service=employees)
    presenter.refresh()
    view._presenter = presenter  # keep alive: Qt drops connections to a collected QObject
    view._employees = employees
    return view, service


def test_timesheet_dropdown_and_employee_column(ts_page):
    view, service = ts_page
    combo = view.employee_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["Me", "Everyone", "Ankush"]
    view._employees.get_employees.assert_called_once_with(include_self=False)
    assert view.table.columnCount() == 7 and view.table.item(0, 1).text() == "Ankush"
    first = service.get_timesheets.call_args.kwargs
    assert first["employee"] is None and first["all_employees"] is False


def test_timesheet_everyone_and_a_person_reach_the_service(ts_page):
    view, service = ts_page
    view.employee_combo.setCurrentIndex(1)
    kwargs = service.get_timesheets.call_args.kwargs
    assert kwargs["all_employees"] is True and kwargs["employee"] is None
    view.employee_combo.setCurrentIndex(2)
    kwargs = service.get_timesheets.call_args.kwargs
    assert kwargs["employee"] == "a@x.ai" and kwargs["all_employees"] is False


def test_search_matches_the_employee_name(ts_page):
    view, _ = ts_page
    view.search_input.setText("ankush")
    assert view.table.rowCount() == 1
    view.search_input.setText("nobody")
    assert view.table.rowCount() == 0


def _detail_presenter(session, owner):
    from src.ui.timesheet_detail_presenter import TimesheetDetailPresenter
    presenter = TimesheetDetailPresenter.__new__(TimesheetDetailPresenter)
    presenter.view = MagicMock()
    presenter.service = MagicMock()
    presenter.service.auth_service.getSession.return_value = session
    presenter._current_name = "TS-1"
    detail = {"name": "TS-1", "employee": owner, "employee_name": "Ankush", "workflow_state": "Pending"}
    presenter._on_result_ready(detail)
    return presenter.view, detail


def test_someone_elses_timesheet_is_shown_read_only():
    view, detail = _detail_presenter("me@x.ai", "a@x.ai")
    view.display_timesheet_detail.assert_called_once_with(detail, read_only_note="Viewing Ankush's timesheet: read only.")


def test_my_own_timesheet_stays_editable():
    view, detail = _detail_presenter("me@x.ai", "me@x.ai")
    view.display_timesheet_detail.assert_called_once_with(detail)


def test_read_only_note_locks_every_action():
    from PySide6.QtWidgets import QApplication
    from src.ui.views.timesheet_detail_view import TimesheetDetailView
    QApplication.instance() or QApplication([])
    v = TimesheetDetailView()
    detail = {"name": "TS-1", "workflow_state": "Pending", "time_logs": [
        {"name": "r1", "idx": 1, "activity_type": "Dev", "from_time": "a", "to_time": "b", "hours": 1}]}
    v.display_timesheet_detail(detail)
    assert v.is_editable and v.submit_btn.isEnabled()
    v.display_timesheet_detail(detail, read_only_note="Viewing Ankush's timesheet: read only.")
    assert not v.is_editable and not v.submit_btn.isEnabled() and not v.delete_timesheet_btn.isEnabled()
    assert "read only" in v.actions_note.text()
