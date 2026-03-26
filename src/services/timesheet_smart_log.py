import time
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.services.timesheet_shared import TimesheetServiceError


def build_smart_log_state_from_doc(raw_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build smart-log defaults and merge state from one raw timesheet doc."""
    if not isinstance(raw_doc, dict):
        return None

    last_row = get_last_time_log(raw_doc.get("time_logs"))
    if not last_row:
        return None

    return {
        "timesheet_name": raw_doc.get("name"),
        "row_name": last_row.get("name"),
        "project_id": last_row.get("project"),
        "project_name": last_row.get("project_name"),
        "activity_name": last_row.get("activity_type") or "",
        "description": last_row.get("description") or "",
        "is_billable": bool(last_row.get("is_billable")),
        "timestamp": last_row.get("to_time") or last_row.get("from_time"),
    }


def build_new_timesheet_doc(template: Dict[str, Any], day: date) -> Dict[str, Any]:
    """Create a new unsaved timesheet doc by seeding stable fields from a template."""
    current_dt = datetime.now()
    day_str = day.isoformat()
    doc = deepcopy(template)
    doc.update(
        {
            "name": f"new-timesheet-{int(time.time() * 1000)}",
            "creation": format_doc_datetime(current_dt, include_microseconds=True),
            "modified": format_doc_datetime(current_dt, include_microseconds=True),
            "modified_by": template.get("modified_by") or template.get("owner"),
            "status": "Draft",
            "workflow_state": template.get("workflow_state") or "Pending",
            "start_date": day_str,
            "end_date": day_str,
            "total_hours": 0.0,
            "total_billable_hours": 0.0,
            "base_total_billable_amount": 0.0,
            "base_total_billed_amount": 0.0,
            "base_total_costing_amount": 0.0,
            "total_billed_hours": 0.0,
            "total_billable_amount": 0.0,
            "total_billed_amount": 0.0,
            "total_costing_amount": 0.0,
            "per_billed": 0.0,
            "time_logs": [],
        }
    )
    return doc


def apply_smart_log_update_to_doc(
    timesheet_doc: Dict[str, Any],
    previous_state: Optional[Dict[str, Any]],
    project_id: str,
    project_name: str,
    activity: str,
    description: str,
    is_billable: bool,
    interval_seconds: int,
    current_dt: datetime,
    employee: str,
    is_new_doc: bool,
) -> Dict[str, Any]:
    """Apply one smart-log save to a raw timesheet doc payload."""
    previous_dt = coerce_optional_datetime(previous_state.get("timestamp") if previous_state else None)
    interval_hours = round(interval_seconds / 3600, 6)
    time_logs = list(timesheet_doc.get("time_logs") or [])
    timesheet_doc["time_logs"] = time_logs

    if should_merge_with_previous(
        previous_state=previous_state,
        timesheet_name=timesheet_doc.get("name"),
        project_id=project_id,
        activity=activity,
        description=description,
        is_billable=is_billable,
    ):
        merge_into_existing_time_log(
            time_logs=time_logs,
            previous_state=previous_state,
            project_id=project_id,
            project_name=project_name,
            activity=activity,
            description=description,
            is_billable=is_billable,
            current_dt=current_dt,
            employee=employee,
            interval_hours=interval_hours,
        )
    else:
        time_logs.append(
            build_new_smart_log_row(
                timesheet_name=str(timesheet_doc["name"]),
                time_logs=time_logs,
                previous_dt=previous_dt,
                current_dt=current_dt,
                interval_seconds=interval_seconds,
                interval_hours=interval_hours,
                project_id=project_id,
                project_name=project_name,
                activity=activity,
                description=description,
                is_billable=is_billable,
                owner=timesheet_doc.get("owner") or employee,
            )
        )

    recompute_timesheet_totals(timesheet_doc)
    timesheet_doc["__unsaved"] = 1
    timesheet_doc["modified_by"] = employee
    if is_new_doc:
        timesheet_doc["__islocal"] = 1
        timesheet_doc["modified"] = format_doc_datetime(current_dt, include_microseconds=True)

    return timesheet_doc


def should_merge_with_previous(
    previous_state: Optional[Dict[str, Any]],
    timesheet_name: Optional[str],
    project_id: str,
    activity: str,
    description: str,
    is_billable: bool,
) -> bool:
    """Return whether the latest smart-log can extend the previous row."""
    return (
        previous_state is not None
        and previous_state.get("timesheet_name") == timesheet_name
        and previous_state.get("project_id") == project_id
        and previous_state.get("activity_name") == activity
        and previous_state.get("description") == description
        and bool(previous_state.get("is_billable")) == is_billable
    )


def merge_into_existing_time_log(
    time_logs: List[Dict[str, Any]],
    previous_state: Optional[Dict[str, Any]],
    project_id: str,
    project_name: str,
    activity: str,
    description: str,
    is_billable: bool,
    current_dt: datetime,
    employee: str,
    interval_hours: float,
) -> None:
    """Extend the previously saved row when the new log matches its identity."""
    target_row = find_time_log_by_name(time_logs, previous_state.get("row_name") if previous_state else None)
    if target_row is None:
        raise TimesheetServiceError("Could not find the previous timesheet row to update.")

    start_dt = coerce_optional_datetime(target_row.get("from_time"))
    previous_to_dt = coerce_optional_datetime(target_row.get("to_time"))
    if start_dt and previous_to_dt and previous_to_dt < start_dt:
        raise TimesheetServiceError("Existing timesheet row has invalid time boundaries.")
    if previous_to_dt and current_dt < previous_to_dt:
        raise TimesheetServiceError("New smart-log time cannot be earlier than the existing row end time.")

    target_row.update(
        {
            "project": project_id,
            "project_name": project_name,
            "activity_type": activity,
            "description": description,
            "is_billable": 1 if is_billable else 0,
            "to_time": format_doc_datetime(current_dt),
            "modified": format_doc_datetime(current_dt, include_microseconds=True),
            "modified_by": employee,
        }
    )

    hours = compute_hours(start_dt, current_dt) if start_dt else interval_hours
    target_row["hours"] = hours
    target_row["billing_hours"] = hours if is_billable else 0.0


def build_new_smart_log_row(
    timesheet_name: str,
    time_logs: List[Dict[str, Any]],
    previous_dt: Optional[datetime],
    current_dt: datetime,
    interval_seconds: int,
    interval_hours: float,
    project_id: str,
    project_name: str,
    activity: str,
    description: str,
    is_billable: bool,
    owner: str,
) -> Dict[str, Any]:
    """Create a new smart-log row using either the previous end time or the interval."""
    from_dt, to_dt, hours = resolve_new_time_log_window(
        previous_dt=previous_dt,
        current_dt=current_dt,
        interval_seconds=interval_seconds,
        interval_hours=interval_hours,
    )
    return build_time_log_row(
        parent_name=timesheet_name,
        current_dt=to_dt,
        from_dt=from_dt,
        hours=hours,
        project_id=project_id,
        project_name=project_name,
        activity=activity,
        description=description,
        is_billable=is_billable,
        idx=len(time_logs) + 1,
        owner=owner,
    )


def resolve_new_time_log_window(
    previous_dt: Optional[datetime],
    current_dt: datetime,
    interval_seconds: int,
    interval_hours: float,
) -> Tuple[datetime, datetime, float]:
    """Return the start, end, and hours for a new smart-log row."""
    if previous_dt is not None and previous_dt.date() == current_dt.date():
        if current_dt < previous_dt:
            raise TimesheetServiceError("New smart-log time cannot be earlier than the previous row end time.")
        return previous_dt, current_dt, compute_hours(previous_dt, current_dt)

    from_dt = current_dt - interval_delta(interval_seconds)
    return from_dt, current_dt, interval_hours


def build_time_log_row(
    parent_name: str,
    current_dt: datetime,
    from_dt: datetime,
    hours: float,
    project_id: str,
    project_name: str,
    activity: str,
    description: str,
    is_billable: bool,
    idx: int,
    owner: str,
) -> Dict[str, Any]:
    """Build one Timesheet Detail row payload."""
    formatted_current = format_doc_datetime(current_dt, include_microseconds=True)
    return {
        "name": f"new-time-log-{int(time.time() * 1000)}",
        "owner": owner,
        "creation": formatted_current,
        "modified": formatted_current,
        "modified_by": owner,
        "docstatus": 0,
        "idx": idx,
        "activity_type": activity,
        "from_time": format_doc_datetime(from_dt),
        "description": description,
        "expected_hours": 0,
        "to_time": format_doc_datetime(current_dt),
        "hours": hours,
        "completed": 0,
        "project": project_id,
        "project_name": project_name,
        "is_billable": 1 if is_billable else 0,
        "billing_hours": hours if is_billable else 0.0,
        "base_billing_rate": 0.0,
        "base_billing_amount": 0.0,
        "base_costing_rate": 0.0,
        "base_costing_amount": 0.0,
        "billing_rate": 0.0,
        "billing_amount": 0.0,
        "costing_rate": 0.0,
        "costing_amount": 0.0,
        "parent": parent_name,
        "parentfield": "time_logs",
        "parenttype": "Timesheet",
        "doctype": "Timesheet Detail",
    }


def recompute_timesheet_totals(timesheet_doc: Dict[str, Any]) -> None:
    """Recalculate top-level totals from the current time_logs list."""
    total_hours = 0.0
    total_billable_hours = 0.0
    total_billable_amount = 0.0
    total_billed_amount = 0.0
    total_costing_amount = 0.0

    for index, row in enumerate(timesheet_doc.get("time_logs") or [], start=1):
        row["idx"] = index
        total_hours += float(row.get("hours") or 0.0)
        total_billable_hours += float(row.get("billing_hours") or 0.0)
        total_billable_amount += float(row.get("billing_amount") or 0.0)
        total_billed_amount += float(row.get("base_billing_amount") or 0.0)
        total_costing_amount += float(row.get("costing_amount") or 0.0)

    timesheet_doc["total_hours"] = total_hours
    timesheet_doc["total_billable_hours"] = total_billable_hours
    timesheet_doc["total_billable_amount"] = total_billable_amount
    timesheet_doc["total_billed_amount"] = total_billed_amount
    timesheet_doc["total_costing_amount"] = total_costing_amount
    timesheet_doc["base_total_billable_amount"] = total_billable_amount
    timesheet_doc["base_total_billed_amount"] = total_billed_amount
    timesheet_doc["base_total_costing_amount"] = total_costing_amount
    timesheet_doc["total_billed_hours"] = 0.0
    timesheet_doc["per_billed"] = 0.0


def get_last_time_log(raw_time_logs: Any) -> Optional[Dict[str, Any]]:
    """Return the latest time log row from a raw timesheet doc."""
    if not isinstance(raw_time_logs, list) or not raw_time_logs:
        return None

    valid_rows = [row for row in raw_time_logs if isinstance(row, dict)]
    if not valid_rows:
        return None
    valid_rows.sort(key=lambda row: row.get("to_time") or row.get("from_time") or "")
    return valid_rows[-1]


def find_time_log_by_name(
    raw_time_logs: List[Dict[str, Any]],
    row_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Find one time log row by its name."""
    if not row_name:
        return None
    for row in raw_time_logs:
        if row.get("name") == row_name:
            return row
    return None


def coerce_datetime(value: Optional[Any]) -> datetime:
    """Convert supported save timestamps into a datetime."""
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise TimesheetServiceError(f"Invalid save timestamp: {value}") from exc
    raise TimesheetServiceError(f"Unsupported save timestamp type: {type(value).__name__}")


def coerce_optional_datetime(value: Optional[Any]) -> Optional[datetime]:
    """Convert an optional date/time string into a datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise TimesheetServiceError(f"Invalid timesheet datetime value: {value}") from exc
    raise TimesheetServiceError(f"Unsupported timesheet datetime type: {type(value).__name__}")


def interval_delta(interval_seconds: int) -> timedelta:
    """Return a timedelta for the configured smart-log interval."""
    return timedelta(seconds=interval_seconds)


def compute_hours(from_dt: datetime, to_dt: datetime) -> float:
    """Return non-negative elapsed hours between two datetimes."""
    delta_seconds = (to_dt - from_dt).total_seconds()
    if delta_seconds <= 0:
        return 0.0
    return round(delta_seconds / 3600, 6)


def format_doc_datetime(
    value: datetime,
    include_microseconds: bool = False,
) -> str:
    """Format datetimes the way Frappe docs expect."""
    if include_microseconds:
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return value.strftime("%Y-%m-%d %H:%M:%S")
