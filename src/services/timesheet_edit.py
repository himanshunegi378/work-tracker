"""Pure helpers that change a raw Timesheet doc (no network). Used by TimesheetService.

Only Draft timesheets that are still in the "Pending" workflow state can be
changed; anything else has been handed over for approval.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.timesheet_shared import TimesheetServiceError
from src.services.timesheet_smart_log import (
    coerce_optional_datetime,
    compute_hours,
    find_time_log_by_name,
    format_doc_datetime,
    recompute_timesheet_totals,
)

EDITABLE_WORKFLOW_STATES = ("Pending", "", None)


def ensure_editable(doc: Dict[str, Any]) -> None:
    """Refuse changes to submitted/approved timesheets with a clear message."""
    state = doc.get("workflow_state")
    if int(doc.get("docstatus") or 0) != 0 or state not in EDITABLE_WORKFLOW_STATES:
        raise TimesheetServiceError(
            f"{doc.get('name')} is {state or 'not a draft'}: only Pending drafts can be changed."
        )


def _require_row(doc: Dict[str, Any], row_name: str) -> Dict[str, Any]:
    row = find_time_log_by_name(doc.get("time_logs") or [], row_name)
    if row is None:
        raise TimesheetServiceError(f"Time log '{row_name}' was not found in {doc.get('name')}.")
    return row


def find_overlap(rows: List[Dict[str, Any]], target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return another row whose time range overlaps `target`, if any (placeholders are ignored)."""
    start, end = coerce_optional_datetime(target.get("from_time")), coerce_optional_datetime(target.get("to_time"))
    if start is None or end is None:
        return None
    for other in rows:
        if other is target or other.get("name") == target.get("name"):
            continue
        o_start, o_end = coerce_optional_datetime(other.get("from_time")), coerce_optional_datetime(other.get("to_time"))
        if o_start is None or o_end is None or o_start == o_end:
            continue
        if start < o_end and end > o_start:
            return other
    return None


def apply_time_log_changes(
    doc: Dict[str, Any],
    row_name: str,
    employee: str,
    *,
    description: Optional[str] = None,
    activity: Optional[str] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    is_billable: Optional[bool] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Change one time-log row in place and refresh the totals. Returns the doc."""
    ensure_editable(doc)
    row = _require_row(doc, row_name)

    if description is not None:
        if not description.strip():
            raise TimesheetServiceError("Description cannot be empty.")
        row["description"] = description.strip()
    if activity is not None:
        row["activity_type"] = activity
    if project_id is not None:
        if not project_name:
            raise TimesheetServiceError("Changing the project needs both its id and name.")
        row["project"], row["project_name"] = project_id, project_name
    if is_billable is not None:
        row["is_billable"] = 1 if is_billable else 0

    if from_time is not None or to_time is not None:
        start = from_time or coerce_optional_datetime(row.get("from_time"))
        end = to_time or coerce_optional_datetime(row.get("to_time"))
        if start is None or end is None:
            raise TimesheetServiceError("The entry has no start or end time to change.")
        if end <= start:
            raise TimesheetServiceError("The end time must be after the start time.")
        row["from_time"], row["to_time"] = format_doc_datetime(start), format_doc_datetime(end)
        row["hours"] = compute_hours(start, end)

    # billing hours always follow the row's current hours and billable flag
    row["billing_hours"] = float(row.get("hours") or 0.0) if row.get("is_billable") else 0.0

    clash = find_overlap(doc.get("time_logs") or [], row)
    if clash is not None:
        raise TimesheetServiceError(
            f"That overlaps another entry ({str(clash.get('from_time'))[11:16]}-{str(clash.get('to_time'))[11:16]})."
        )

    row["modified_by"] = employee
    _finish(doc, employee)
    return doc


def remove_time_log(doc: Dict[str, Any], row_name: str, employee: str) -> Dict[str, Any]:
    """Delete one time-log row in place. A timesheet must keep at least one entry."""
    ensure_editable(doc)
    rows = doc.get("time_logs") or []
    row = _require_row(doc, row_name)
    if len(rows) <= 1:
        raise TimesheetServiceError(
            "That is the only entry; delete the whole timesheet instead (`samta-tracker timesheets rm`)."
        )
    doc["time_logs"] = [r for r in rows if r is not row]
    _finish(doc, employee)
    return doc


def _finish(doc: Dict[str, Any], employee: str) -> None:
    recompute_timesheet_totals(doc)
    doc["__unsaved"] = 1
    doc["modified_by"] = employee
