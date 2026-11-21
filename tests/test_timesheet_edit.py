import copy
import json
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.api import ApiClientError
from src.services.timesheet_edit import apply_time_log_changes, ensure_editable, find_overlap, remove_time_log
from src.services.timesheet_service import TimesheetService
from src.services.timesheet_shared import TimesheetServiceError


def row(name, start, end, hours, billable=0, desc="work", idx=1):
    return {"name": name, "idx": idx, "activity_type": "Execution", "project": "PROJ-1", "project_name": "P",
            "description": desc, "from_time": f"2026-11-21 {start}", "to_time": f"2026-11-21 {end}",
            "hours": hours, "is_billable": billable, "billing_hours": hours if billable else 0.0,
            "billing_amount": 0.0, "costing_amount": 0.0}


def make_doc(state="Pending", docstatus=0):
    rows = [row("r1", "09:00:00", "10:00:00", 1.0, idx=1), row("r2", "10:00:01", "12:00:00", 1.9997, idx=2, desc="second")]
    return {"name": "TS-1", "docstatus": docstatus, "workflow_state": state, "status": "Draft",
            "owner": "me@x.y", "time_logs": rows}


# ── pure helpers ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("state,docstatus", [("Submitted", 0), ("Approved", 1), ("Pending", 1), ("Rejected", 0)])
def test_only_pending_drafts_are_editable(state, docstatus):
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        ensure_editable(make_doc(state, docstatus))
    ensure_editable(make_doc())


def test_changing_text_fields_and_billable_updates_billing_hours():
    doc = apply_time_log_changes(make_doc(), "r2", "me@x.y", description=" new text ", activity="Review",
                                 project_id="PROJ-9", project_name="Nine", is_billable=True)
    changed = doc["time_logs"][1]
    assert changed["description"] == "new text" and changed["activity_type"] == "Review"
    assert (changed["project"], changed["project_name"]) == ("PROJ-9", "Nine")
    assert changed["is_billable"] == 1 and changed["billing_hours"] == changed["hours"]
    assert doc["total_billable_hours"] == pytest.approx(1.9997) and doc["__unsaved"] == 1


def test_untouched_rows_stay_exactly_as_they_were():
    before = make_doc()
    doc = apply_time_log_changes(copy.deepcopy(before), "r2", "me@x.y", description="x")
    assert doc["time_logs"][0] == before["time_logs"][0]


def test_changing_times_recomputes_hours_and_totals():
    doc = apply_time_log_changes(make_doc(), "r1", "me@x.y", to_time=datetime(2026, 11, 21, 9, 30))
    changed = doc["time_logs"][0]
    assert changed["to_time"] == "2026-11-21 09:30:00" and changed["hours"] == 0.5
    assert doc["total_hours"] == pytest.approx(0.5 + 1.9997)


def test_unbilling_zeroes_billing_hours():
    doc = make_doc()
    doc["time_logs"][0].update(is_billable=1, billing_hours=1.0)
    apply_time_log_changes(doc, "r1", "me@x.y", is_billable=False)
    assert doc["time_logs"][0]["billing_hours"] == 0.0 and doc["total_billable_hours"] == 0.0


@pytest.mark.parametrize("kwargs,message", [
    ({"description": "  "}, "cannot be empty"),
    ({"project_id": "PROJ-9"}, "id and name"),
    ({"from_time": datetime(2026, 11, 21, 11, 0)}, "after the start"),
    ({"to_time": datetime(2026, 11, 21, 8, 0)}, "after the start"),
])
def test_invalid_changes_are_rejected(kwargs, message):
    with pytest.raises(TimesheetServiceError, match=message):
        apply_time_log_changes(make_doc(), "r1", "me@x.y", **kwargs)


def test_overlapping_another_entry_is_rejected():
    with pytest.raises(TimesheetServiceError, match="overlaps another entry"):
        apply_time_log_changes(make_doc(), "r1", "me@x.y", to_time=datetime(2026, 11, 21, 10, 30))


def test_touching_entries_do_not_overlap_and_placeholders_are_ignored():
    doc = make_doc()
    doc["time_logs"].append(row("r3", "09:30:00", "09:30:00", 0.0, idx=3))  # zero-length placeholder
    apply_time_log_changes(doc, "r1", "me@x.y", to_time=datetime(2026, 11, 21, 10, 0))
    assert find_overlap(doc["time_logs"], doc["time_logs"][0]) is None


def test_unknown_row_and_locked_timesheet():
    with pytest.raises(TimesheetServiceError, match="not found"):
        apply_time_log_changes(make_doc(), "nope", "me@x.y", description="x")
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        apply_time_log_changes(make_doc("Submitted"), "r1", "me@x.y", description="x")


def test_remove_row_renumbers_and_recomputes():
    doc = remove_time_log(make_doc(), "r1", "me@x.y")
    assert [r["name"] for r in doc["time_logs"]] == ["r2"] and doc["time_logs"][0]["idx"] == 1
    assert doc["total_hours"] == pytest.approx(1.9997)


def test_cannot_remove_the_last_entry_or_from_a_locked_timesheet():
    doc = remove_time_log(make_doc(), "r1", "me@x.y")
    with pytest.raises(TimesheetServiceError, match="only entry"):
        remove_time_log(doc, "r2", "me@x.y")
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        remove_time_log(make_doc("Submitted"), "r1", "me@x.y")


# ── service methods ───────────────────────────────────────────────────────
class Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def make_service(doc=None):
    api = MagicMock()
    api.get_cookies.return_value = {}
    auth = MagicMock()
    auth.getSession.return_value = "me@x.y"
    service = TimesheetService(api, auth)
    api.get.side_effect = lambda *a, **k: Response({"docs": [copy.deepcopy(doc or make_doc())]})
    return service, api


def saved_doc(api):
    return json.loads(dict(urllib.parse.parse_qsl(api.post.call_args.kwargs["data"]))["doc"])


def test_update_time_log_saves_the_changed_doc():
    service, api = make_service()
    api.post.side_effect = lambda *a, **k: Response({"docs": [make_doc()]})
    service.update_time_log("TS-1", "r2", description="edited")
    doc = saved_doc(api)
    assert doc["time_logs"][1]["description"] == "edited" and doc["time_logs"][0]["description"] == "work"
    assert api.post.call_args.args[0].endswith("savedocs")


def test_update_retries_once_after_a_stale_copy_error():
    service, api = make_service()
    stale = ApiClientError("changed", exc_type="TimestampMismatchError")
    api.post.side_effect = [stale, Response({"docs": [make_doc()]})]
    service.update_time_log("TS-1", "r1", description="x")
    assert api.post.call_count == 2 and api.get.call_count == 2  # refetched before the retry


def test_other_save_errors_are_wrapped_and_not_retried():
    service, api = make_service()
    api.post.side_effect = ApiClientError("boom", exc_type="ValidationError")
    with pytest.raises(TimesheetServiceError, match="Failed to update timesheet"):
        service.update_time_log("TS-1", "r1", description="x")
    assert api.post.call_count == 1


def test_update_on_a_submitted_timesheet_never_posts():
    service, api = make_service(make_doc("Submitted"))
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        service.update_time_log("TS-1", "r1", description="x")
    api.post.assert_not_called()


def test_delete_time_log_posts_without_the_row():
    service, api = make_service()
    api.post.side_effect = lambda *a, **k: Response({"docs": [make_doc()]})
    service.delete_time_log("TS-1", "r1")
    assert [r["name"] for r in saved_doc(api)["time_logs"]] == ["r2"]


def test_get_workflow_actions():
    service, api = make_service()
    api.post.return_value = Response({"message": [{"action": "Submit"}, {"action": "Cancel"}, {"nope": 1}]})
    assert service.get_workflow_actions("TS-1") == ["Submit", "Cancel"]


def test_submit_applies_the_workflow_action():
    service, api = make_service()
    submitted = make_doc("Submitted", docstatus=0)
    api.post.side_effect = [Response({"message": [{"action": "Submit"}]}), Response({"message": submitted})]
    detail = service.submit_timesheet("TS-1")
    assert detail["workflow_state"] == "Submitted"
    endpoint, kwargs = api.post.call_args.args[0], api.post.call_args.kwargs
    assert endpoint.endswith("apply_workflow")
    assert dict(urllib.parse.parse_qsl(kwargs["data"]))["action"] == "Submit"


def test_submit_refuses_when_the_action_is_not_offered_or_the_doc_is_locked():
    service, api = make_service()
    api.post.return_value = Response({"message": [{"action": "Approve"}]})
    with pytest.raises(TimesheetServiceError, match="cannot be submitted.*Approve"):
        service.submit_timesheet("TS-1")
    locked, api2 = make_service(make_doc("Submitted"))
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        locked.submit_timesheet("TS-1")
    api2.post.assert_not_called()


def test_submit_refuses_an_empty_timesheet():
    doc = make_doc()
    doc["time_logs"] = []
    service, api = make_service(doc)
    with pytest.raises(TimesheetServiceError, match="no time logs"):
        service.submit_timesheet("TS-1")


def test_delete_timesheet_only_for_pending_drafts():
    service, api = make_service()
    service.delete_timesheet("TS-1")
    api.delete.assert_called_once_with("/api/resource/Timesheet/TS-1")
    locked, api2 = make_service(make_doc("Approved"))
    with pytest.raises(TimesheetServiceError, match="only Pending drafts"):
        locked.delete_timesheet("TS-1")
    api2.delete.assert_not_called()


def test_delete_timesheet_wraps_api_errors():
    service, api = make_service()
    api.delete.side_effect = ApiClientError("no")
    with pytest.raises(TimesheetServiceError, match="Failed to delete"):
        service.delete_timesheet("TS-1")
