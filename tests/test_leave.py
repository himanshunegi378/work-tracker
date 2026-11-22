import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.services.leave_service import LeaveAuthError, LeaveService

runner = CliRunner()

REPORTVIEW = {"message": {
    "keys": ["name", "leave_type", "from_date", "to_date", "total_leave_days", "status"],
    "values": [["HR-LAP-1", "Sick Leave", "2026-10-14", "2026-10-14", 1.0, "Approved"],
               ["HR-LAP-2", "Privilege Leave", "2026-05-18", "2026-05-22", 5.0, "Open"]],
}}


def make_service(session="me@x.ai"):
    api = MagicMock()
    api.get_cookies.return_value = {}
    api.post.return_value.json.return_value = REPORTVIEW
    auth = MagicMock()
    auth.getSession.return_value = session
    return LeaveService(api, auth), api


def test_service_builds_filters_and_normalizes_rows():
    service, api = make_service()
    rows = service.get_leave_applications(status="Approved", leave_type="Sick Leave",
                                          from_date="2026-01-01", to_date="2026-12-31", start=20, page_length=5)
    assert rows[0] == {"name": "HR-LAP-1", "leave_type": "Sick Leave", "from_date": "2026-10-14",
                       "to_date": "2026-10-14", "total_leave_days": 1.0, "status": "Approved"}
    sent = parse_qs(api.post.call_args.kwargs["data"])
    assert sent["doctype"] == ["Leave Application"]
    assert (sent["start"], sent["page_length"]) == (["20"], ["5"])
    assert json.loads(sent["filters"][0]) == [
        ["Leave Application", "employee", "=", "me@x.ai"],
        ["Leave Application", "status", "=", "Approved"],
        ["Leave Application", "leave_type", "=", "Sick Leave"],
        ["Leave Application", "to_date", ">=", "2026-01-01"],
        ["Leave Application", "from_date", "<=", "2026-12-31"],
    ]


def test_service_requires_a_logged_in_user():
    service, _ = make_service(session=None)
    with pytest.raises(LeaveAuthError):
        service.get_leave_applications()


def test_service_empty_message_gives_no_rows():
    service, api = make_service()
    api.post.return_value.json.return_value = {"message": []}
    assert service.get_leave_applications() == []


def test_service_leave_types_lists_names():
    service, api = make_service()
    api.get.return_value.json.return_value = {"message": [{"name": "Sick Leave"}, {"name": "Privilege Leave"}, {}]}
    assert service.get_leave_types() == ["Sick Leave", "Privilege Leave"]
    assert api.get.call_args.kwargs["params"]["doctype"] == "Leave Type"


BALANCE = {"message": {"leave_allocation": {
    "Sick Leave": {"total_leaves": 6.0, "expired_leaves": 0, "leaves_taken": 5.0,
                   "leaves_pending_approval": 0.0, "remaining_leaves": 1.0},
    "Privilege Leave": {"total_leaves": 15.0, "leaves_taken": 8.0, "remaining_leaves": 7.0},
}, "leave_approver": "x@y.ai", "lwps": ["Leave Without Pay"]}}


def test_service_leave_balance_rows_and_request():
    service, api = make_service()
    api.post.return_value.json.return_value = BALANCE
    rows = service.get_leave_balance(on_date="2026-11-22")
    assert rows[0] == {"leave_type": "Sick Leave", "total_leaves": 6.0, "leaves_taken": 5.0,
                       "leaves_pending_approval": 0.0, "expired_leaves": 0, "remaining_leaves": 1.0}
    assert rows[1]["leaves_pending_approval"] == 0 and rows[1]["remaining_leaves"] == 7.0
    sent = parse_qs(api.post.call_args.kwargs["data"])
    assert sent == {"employee": ["me@x.ai"], "date": ["2026-11-22"]}


def test_service_leave_balance_empty_and_unauthenticated():
    service, api = make_service()
    api.post.return_value.json.return_value = {"message": {}}
    assert service.get_leave_balance() == []
    with pytest.raises(LeaveAuthError):
        make_service(session=None)[0].get_leave_balance()


class FakeLeave:
    def __init__(self):
        self.calls = []

    def get_leave_applications(self, **kwargs):
        self.calls.append(kwargs)
        rows = [{"name": "HR-LAP-1", "employee_name": "Himanshu Negi", "leave_type": "Sick Leave", "from_date": "2026-10-14",
                 "to_date": "2026-10-14", "total_leave_days": 1.0, "status": "Approved"}]
        return rows[kwargs.get("start", 0):][: kwargs.get("page_length", 20)]

    def get_leave_balance(self, **kwargs):
        self.calls.append(("balance", kwargs))
        return [{"leave_type": "Sick Leave", "total_leaves": 6.0, "leaves_taken": 5.0,
                 "leaves_pending_approval": 0.0, "expired_leaves": 0, "remaining_leaves": 1.0}]


@pytest.fixture
def leave(monkeypatch):
    fake = FakeLeave()
    monkeypatch.setattr("src.cli.commands.leave.get_context", lambda c, base_url=None: SimpleNamespace(leave=fake))
    return fake


def run(*args):
    return runner.invoke(app, list(args))


def test_cli_leave_list_table(leave):
    result = run("leave", "list")
    assert result.exit_code == 0
    assert "HR-LAP-1" in result.output and "Himanshu Negi" in result.output and "EMPLOYEE" in result.output and "Sick Leave" in result.output and "STATUS" in result.output


def test_cli_leave_list_filters_are_passed_to_service(leave):
    run("leave", "list", "--status", "approved", "--type", "Sick Leave", "--from", "2026-01-01", "--to", "2026-12-31", "-n", "5", "--page", "2")
    call = leave.calls[0]
    assert call["status"] == "Approved" and call["leave_type"] == "Sick Leave"
    assert str(call["from_date"]) == "2026-01-01" and str(call["to_date"]) == "2026-12-31"
    assert (call["start"], call["page_length"]) == (5, 5)


def test_cli_leave_list_json_and_quiet(leave):
    assert json.loads(run("--json", "leave", "list").output)[0]["name"] == "HR-LAP-1"
    assert run("-q", "leave", "list").output.strip() == "HR-LAP-1"


def test_cli_leave_list_rejects_inverted_range(leave):
    result = run("leave", "list", "--from", "2026-12-01", "--to", "2026-01-01")
    assert result.exit_code != 0 and not leave.calls


def test_cli_leave_balance_table_and_date(leave):
    result = run("leave", "balance", "--date", "2026-12-01")
    assert result.exit_code == 0
    assert "REMAINING" in result.output and "Sick Leave" in result.output
    assert str(leave.calls[0][1]["on_date"]) == "2026-12-01"


def test_cli_leave_balance_json_and_quiet(leave):
    assert json.loads(run("--json", "leave", "balance").output)[0]["remaining_leaves"] == 1.0
    assert run("-q", "leave", "balance").output.strip() == "Sick Leave"
