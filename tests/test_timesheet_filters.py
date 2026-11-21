import json
import sys
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.timesheet_service import TimesheetService


def _service():
    api = MagicMock()
    api.get_cookies.return_value = {}
    api.post.return_value = MagicMock(json=lambda: {"message": {"keys": ["name"], "values": []}})
    auth = MagicMock()
    auth.getSession.return_value = "me@example.com"
    return TimesheetService(api, auth), api


def _filters(api):
    payload = dict(urllib.parse.parse_qsl(api.post.call_args.kwargs["data"]))
    return json.loads(payload["filters"])


def test_no_extra_filters_keeps_old_behaviour():
    service, api = _service()
    service.get_timesheets()
    assert _filters(api) == [["Timesheet", "employee", "=", "me@example.com"]]


def test_status_workflow_and_date_filters():
    service, api = _service()
    service.get_timesheets(status="Draft", workflow_state="Pending", from_date="2026-10-01", to_date="2026-10-31")
    assert _filters(api) == [
        ["Timesheet", "employee", "=", "me@example.com"],
        ["Timesheet", "status", "=", "Draft"],
        ["Timesheet", "workflow_state", "=", "Pending"],
        ["Timesheet", "start_date", ">=", "2026-10-01"],
        ["Timesheet", "end_date", "<=", "2026-10-31"],
    ]


def test_covering_date_matches_range_containing_the_day():
    service, api = _service()
    service.get_timesheets(covering_date="2026-10-28")
    assert _filters(api)[1:] == [
        ["Timesheet", "start_date", "<=", "2026-10-28"],
        ["Timesheet", "end_date", ">=", "2026-10-28"],
    ]


def test_employee_override_still_applies_with_filters():
    service, api = _service()
    service.get_timesheets(employee="other@example.com", status="Submitted")
    assert _filters(api)[0] == ["Timesheet", "employee", "=", "other@example.com"]


def test_missing_user_raises_auth_error_that_is_still_a_service_error():
    from src.api import AuthenticationRequiredError
    from src.services.timesheet_shared import TimesheetServiceError

    service, _ = _service()
    service.auth_service.getSession.return_value = None
    try:
        service.get_timesheets()
    except TimesheetServiceError as exc:
        assert isinstance(exc, AuthenticationRequiredError)
    else:
        raise AssertionError("expected an error")
