import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.api import ApiClientError
from src.services.timesheet_service import TimesheetService, TimesheetServiceError


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestTimesheetService(unittest.TestCase):
    def _make_service(self):
        api_client = MagicMock()
        api_client.get_cookies.return_value = {}
        auth_service = MagicMock()
        auth_service.getSession.return_value = "user@example.com"
        service = TimesheetService(api_client, auth_service)
        return service, api_client, auth_service

    def test_get_timesheets_normalizes_reportview_rows(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "message": {
                    "keys": ["name", "status", "start_date", "end_date", "total_hours"],
                    "values": [
                        ["TS-0001", "Draft", "2026-03-25", "2026-03-25", 8],
                        ["TS-0002", "Submitted", "2026-03-24", "2026-03-24", 7.5],
                    ],
                }
            }
        )

        result = service.get_timesheets()

        self.assertEqual(
            result,
            [
                {
                    "name": "TS-0001",
                    "status": "Draft",
                    "start_date": "2026-03-25",
                    "end_date": "2026-03-25",
                    "total_hours": 8,
                },
                {
                    "name": "TS-0002",
                    "status": "Submitted",
                    "start_date": "2026-03-24",
                    "end_date": "2026-03-24",
                    "total_hours": 7.5,
                },
            ],
        )

    def test_get_timesheets_uses_authenticated_user_by_default(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse({"message": {"keys": [], "values": []}})

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.get_timesheets(start=40, page_length=10)

        auth_service.getSession.assert_called_once_with()
        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        self.assertEqual(payload["doctype"], "Timesheet")
        self.assertEqual(payload["start"], "40")
        self.assertEqual(payload["page_length"], "10")
        self.assertEqual(
            json.loads(urllib_unquote(payload["filters"])),
            [["Timesheet", "employee", "=", "user@example.com"]],
        )

    def test_get_timesheets_uses_explicit_employee_override(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse({"message": {"keys": [], "values": []}})

        service.get_timesheets(employee="override@example.com")

        auth_service.getSession.assert_not_called()
        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        self.assertEqual(
            json.loads(urllib_unquote(payload["filters"])),
            [["Timesheet", "employee", "=", "override@example.com"]],
        )

    def test_get_timesheets_raises_when_no_user_available(self):
        service, api_client, auth_service = self._make_service()
        auth_service.getSession.return_value = None

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.get_timesheets()

        self.assertIn("No authenticated user", str(ctx.exception))
        api_client.post.assert_not_called()

    def test_get_timesheets_wraps_api_errors(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.side_effect = ApiClientError("boom")

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.get_timesheets()

        self.assertIn("Failed to fetch timesheets", str(ctx.exception))

    def test_get_timesheets_raises_for_malformed_payload(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse({"message": {"keys": ["name"]}})

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.get_timesheets()

        self.assertIn("missing message.keys or message.values", str(ctx.exception))

    def test_normalize_reportview_response_returns_empty_rows_for_empty_message_list(self):
        service, api_client, auth_service = self._make_service()

        result = service._normalize_reportview_response(
            {"message": []},
            source="_get_or_prepare_timesheet_for_day",
        )

        self.assertEqual(result, [])

    def test_get_timesheets_logs_source_and_payload_for_missing_message_object(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse({"exc_type": "ValidationError"})

        with self.assertLogs("src.services.timesheet_service", level="ERROR") as captured:
            with self.assertRaises(TimesheetServiceError):
                service.get_timesheets()

        combined = "\n".join(captured.output)
        self.assertIn("get_timesheets", combined)
        self.assertIn("missing message object", combined)
        self.assertIn('"exc_type": "ValidationError"', combined)

    def test_get_timesheets_sends_csrf_header_when_available(self):
        service, api_client, auth_service = self._make_service()
        api_client.get_cookies.return_value = {"csrf_token": "csrf-123"}
        api_client.post.return_value = FakeResponse({"message": {"keys": [], "values": []}})

        service.get_timesheets()

        _, kwargs = api_client.post.call_args
        self.assertEqual(kwargs["headers"]["x-frappe-csrf-token"], "csrf-123")

    def test_get_timesheet_detail_normalizes_parent_and_time_logs(self):
        service, api_client, auth_service = self._make_service()
        api_client.get.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-2026-01786",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "employee_name": "Himanshu Singh Negi",
                        "department": "Technology - SIPL",
                        "company": "Samta Infotech Pvt Ltd",
                        "currency": "INR",
                        "start_date": "2026-03-24",
                        "end_date": "2026-03-24",
                        "total_hours": 8,
                        "total_billable_hours": 8,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [
                            {
                                "name": "row-1",
                                "activity_type": "Execution",
                                "project": "PROJ-0010",
                                "project_name": "IDGI",
                                "from_time": "2026-03-24 09:16:15",
                                "to_time": "2026-03-24 15:46:15",
                                "hours": 6.5,
                                "is_billable": 1,
                                "description": "Worked on delivery",
                            }
                        ],
                    }
                ]
            }
        )

        result = service.get_timesheet_detail("TS-2026-01786")

        self.assertEqual(result["name"], "TS-2026-01786")
        self.assertEqual(result["employee_name"], "Himanshu Singh Negi")
        self.assertEqual(len(result["time_logs"]), 1)
        self.assertEqual(result["time_logs"][0]["activity_type"], "Execution")
        self.assertEqual(result["time_logs"][0]["project_name"], "IDGI")

    def test_get_timesheet_detail_builds_correct_request(self):
        service, api_client, auth_service = self._make_service()
        api_client.get.return_value = FakeResponse({"docs": [{"name": "TS-1", "time_logs": []}]})

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.get_timesheet_detail("TS-1")

        _, kwargs = api_client.get.call_args
        self.assertEqual(kwargs["params"]["doctype"], "Timesheet")
        self.assertEqual(kwargs["params"]["name"], "TS-1")
        self.assertEqual(kwargs["headers"]["x-frappe-doctype"], "Timesheet")

    def test_get_timesheet_detail_raises_for_missing_docs(self):
        service, api_client, auth_service = self._make_service()
        api_client.get.return_value = FakeResponse({"docs": []})

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.get_timesheet_detail("TS-1")

        self.assertIn("missing docs", str(ctx.exception))

    def test_get_timesheet_detail_wraps_api_errors(self):
        service, api_client, auth_service = self._make_service()
        api_client.get.side_effect = ApiClientError("detail boom")

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.get_timesheet_detail("TS-1")

        self.assertIn("Failed to fetch timesheet detail", str(ctx.exception))

    def test_save_timesheet_log_appends_new_row_from_previous_to_current_time(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-TODAY",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "title": "User",
                        "employee": "user@example.com",
                        "employee_name": "User",
                        "department": "Tech",
                        "company": "Samta",
                        "currency": "INR",
                        "start_date": "2026-03-25",
                        "end_date": "2026-03-25",
                        "total_hours": 0.5,
                        "total_billable_hours": 0.5,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [],
                    }
                ]
            }
        )

        service.get_latest_smart_log_state = MagicMock(
            return_value={
                "timesheet_name": "TS-TODAY",
                "row_name": "prev-row",
                "project_id": "PROJ-OLD",
                "project_name": "Old",
                "activity_name": "Planning",
                "description": "Older work",
                "is_billable": True,
                "timestamp": "2026-03-25 09:30:00",
            }
        )
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified": "2026-03-25 19:34:17.275100",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [],
                },
                False,
            )
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(len(doc["time_logs"]), 1)
        self.assertEqual(doc["time_logs"][0]["from_time"], "2026-03-25 09:30:00")
        self.assertEqual(doc["time_logs"][0]["to_time"], "2026-03-25 09:45:00")
        self.assertEqual(doc["time_logs"][0]["hours"], 0.25)

    def test_save_timesheet_log_uses_interval_for_first_record_of_day(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-TODAY",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "title": "User",
                        "employee": "user@example.com",
                        "employee_name": "User",
                        "department": "Tech",
                        "company": "Samta",
                        "currency": "INR",
                        "start_date": "2026-03-25",
                        "end_date": "2026-03-25",
                        "total_hours": 0.5,
                        "total_billable_hours": 0.5,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [],
                    }
                ]
            }
        )

        service.get_latest_smart_log_state = MagicMock(return_value=None)
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified": "2026-03-25 19:34:17.275100",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [],
                },
                False,
            )
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(doc["time_logs"][0]["from_time"], "2026-03-25 09:15:00")
        self.assertEqual(doc["time_logs"][0]["to_time"], "2026-03-25 09:45:00")
        self.assertEqual(doc["time_logs"][0]["hours"], 0.5)

    def test_save_timesheet_log_creates_new_day_timesheet_with_only_first_row(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-NEW",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "title": "User",
                        "employee": "user@example.com",
                        "employee_name": "User",
                        "department": "Tech",
                        "company": "Samta",
                        "currency": "INR",
                        "start_date": "2026-03-26",
                        "end_date": "2026-03-26",
                        "total_hours": 0.5,
                        "total_billable_hours": 0.5,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [],
                    }
                ]
            }
        )

        service.get_latest_smart_log_state = MagicMock(
            return_value={
                "timesheet_name": "TS-YESTERDAY",
                "row_name": "prev-row",
                "project_id": "PROJ-OLD",
                "project_name": "Old",
                "activity_name": "Planning",
                "description": "Older work",
                "is_billable": True,
                "timestamp": "2026-03-25 18:30:00",
            }
        )
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "new-timesheet-1700000000",
                    "owner": "user@example.com",
                    "modified": "2026-03-26 09:45:00.000000",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "start_date": "2026-03-26",
                    "end_date": "2026-03-26",
                    "employee": "user@example.com",
                    "employee_name": "User",
                    "department": "Tech",
                    "company": "Samta",
                    "currency": "INR",
                    "time_logs": [],
                },
                True,
            )
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-26 09:45:00",
            )

        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(doc["start_date"], "2026-03-26")
        self.assertEqual(doc["end_date"], "2026-03-26")
        self.assertEqual(doc["__islocal"], 1)
        self.assertEqual(len(doc["time_logs"]), 1)
        self.assertEqual(doc["time_logs"][0]["from_time"], "2026-03-26 09:15:00")
        self.assertEqual(doc["time_logs"][0]["to_time"], "2026-03-26 09:45:00")
        self.assertEqual(doc["time_logs"][0]["project"], "PROJ-0010")
        self.assertEqual(doc["time_logs"][0]["activity_type"], "Execution")
        self.assertEqual(doc["time_logs"][0]["description"], "Worked on feature")

    def test_save_timesheet_log_updates_previous_matching_row(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-TODAY",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "title": "User",
                        "employee": "user@example.com",
                        "employee_name": "User",
                        "department": "Tech",
                        "company": "Samta",
                        "currency": "INR",
                        "start_date": "2026-03-25",
                        "end_date": "2026-03-25",
                        "total_hours": 1.0,
                        "total_billable_hours": 1.0,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [],
                    }
                ]
            }
        )

        service.get_latest_smart_log_state = MagicMock(
            return_value={
                "timesheet_name": "TS-TODAY",
                "row_name": "prev-row",
                "project_id": "PROJ-0010",
                "project_name": "IDGI",
                "activity_name": "Execution",
                "description": "Worked on feature",
                "is_billable": True,
                "timestamp": "2026-03-25 09:30:00",
            }
        )
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified": "2026-03-25 19:34:17.275100",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [
                        {
                            "name": "prev-row",
                            "from_time": "2026-03-25 09:00:00",
                            "to_time": "2026-03-25 09:30:00",
                            "hours": 0.5,
                            "billing_hours": 0.5,
                            "project": "PROJ-0010",
                            "project_name": "IDGI",
                            "activity_type": "Execution",
                            "description": "Worked on feature",
                            "is_billable": 1,
                        }
                    ],
                },
                False,
            )
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(len(doc["time_logs"]), 1)
        self.assertEqual(doc["time_logs"][0]["to_time"], "2026-03-25 09:45:00")
        self.assertEqual(doc["time_logs"][0]["hours"], 0.75)
        self.assertEqual(doc["time_logs"][0]["billing_hours"], 0.75)
        self.assertNotIn("x-frappe-doctype", kwargs["headers"])
        self.assertEqual(doc["modified"], "2026-03-25 19:34:17.275100")

    def test_save_timesheet_log_does_not_merge_when_billable_differs(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.return_value = FakeResponse(
            {
                "docs": [
                    {
                        "name": "TS-TODAY",
                        "workflow_state": "Pending",
                        "status": "Draft",
                        "title": "User",
                        "employee": "user@example.com",
                        "employee_name": "User",
                        "department": "Tech",
                        "company": "Samta",
                        "currency": "INR",
                        "start_date": "2026-03-25",
                        "end_date": "2026-03-25",
                        "total_hours": 0.75,
                        "total_billable_hours": 0.5,
                        "total_billable_amount": 0,
                        "total_billed_amount": 0,
                        "total_costing_amount": 0,
                        "time_logs": [],
                    }
                ]
            }
        )

        service.get_latest_smart_log_state = MagicMock(
            return_value={
                "timesheet_name": "TS-TODAY",
                "row_name": "prev-row",
                "project_id": "PROJ-0010",
                "project_name": "IDGI",
                "activity_name": "Execution",
                "description": "Worked on feature",
                "is_billable": True,
                "timestamp": "2026-03-25 09:30:00",
            }
        )
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified": "2026-03-25 19:34:17.275100",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [
                        {
                            "name": "prev-row",
                            "from_time": "2026-03-25 09:00:00",
                            "to_time": "2026-03-25 09:30:00",
                            "hours": 0.5,
                            "billing_hours": 0.5,
                            "project": "PROJ-0010",
                            "project_name": "IDGI",
                            "activity_type": "Execution",
                            "description": "Worked on feature",
                            "is_billable": 1,
                        }
                    ],
                },
                False,
            )
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=False,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        _, kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(len(doc["time_logs"]), 2)
        self.assertEqual(doc["time_logs"][1]["from_time"], "2026-03-25 09:30:00")
        self.assertEqual(doc["time_logs"][1]["to_time"], "2026-03-25 09:45:00")
        self.assertEqual(doc["time_logs"][1]["hours"], 0.25)
        self.assertEqual(doc["time_logs"][1]["billing_hours"], 0.0)

    def test_save_timesheet_log_retries_once_after_timestamp_mismatch(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.side_effect = [
            ApiClientError(
                "Request failed (HTTP 417): TimestampMismatchError | stale",
                exc_type="TimestampMismatchError",
            ),
            FakeResponse(
                {
                    "docs": [
                        {
                            "name": "TS-TODAY",
                            "workflow_state": "Pending",
                            "status": "Draft",
                            "title": "User",
                            "employee": "user@example.com",
                            "employee_name": "User",
                            "department": "Tech",
                            "company": "Samta",
                            "currency": "INR",
                            "start_date": "2026-03-25",
                            "end_date": "2026-03-25",
                            "total_hours": 1.0,
                            "total_billable_hours": 1.0,
                            "total_billable_amount": 0,
                            "total_billed_amount": 0,
                            "total_costing_amount": 0,
                            "time_logs": [],
                        }
                    ]
                }
            ),
        ]
        service.get_latest_smart_log_state = MagicMock(return_value=None)

        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified": "2026-03-25 19:34:17.275100",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [],
                },
                False,
            )
        )
        service._get_raw_timesheet_doc = MagicMock(
            return_value={
                "name": "TS-TODAY",
                "owner": "user@example.com",
                "modified": "2026-03-25 19:50:20.902137",
                "modified_by": "user@example.com",
                "workflow_state": "Pending",
                "status": "Draft",
                "time_logs": [],
            }
        )

        with patch("src.services.timesheet_service.time.time", return_value=1700000000):
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        self.assertEqual(api_client.post.call_count, 2)
        _, second_kwargs = api_client.post.call_args
        payload = dict(item.split("=", 1) for item in second_kwargs["data"].split("&"))
        doc = json.loads(urllib_unquote(payload["doc"]))
        self.assertEqual(doc["modified"], "2026-03-25 19:50:20.902137")

    def test_save_timesheet_log_surfaces_server_validation_details(self):
        service, api_client, auth_service = self._make_service()
        api_client.post.side_effect = ApiClientError(
            "Request failed (HTTP 417): ValidationError | Row 1: Activity Type is required"
        )
        service.get_latest_smart_log_state = MagicMock(return_value=None)
        service._get_or_prepare_timesheet_for_day = MagicMock(
            return_value=(
                {
                    "name": "TS-TODAY",
                    "owner": "user@example.com",
                    "modified_by": "user@example.com",
                    "workflow_state": "Pending",
                    "status": "Draft",
                    "time_logs": [],
                },
                False,
            )
        )

        with self.assertRaises(TimesheetServiceError) as ctx:
            service.save_timesheet_log(
                project_id="PROJ-0010",
                project_name="IDGI",
                activity="Execution",
                description="Worked on feature",
                is_billable=True,
                interval_seconds=1800,
                saved_at="2026-03-25 09:45:00",
            )

        self.assertIn("HTTP 417", str(ctx.exception))
        self.assertIn("ValidationError", str(ctx.exception))
        self.assertIn("Activity Type is required", str(ctx.exception))


def urllib_unquote(value: str) -> str:
    from urllib.parse import unquote_plus

    return unquote_plus(value)


if __name__ == "__main__":
    unittest.main()
