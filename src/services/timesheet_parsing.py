import json
from typing import Any, Dict, List, Optional

from src.services.timesheet_shared import TimesheetServiceError


def normalize_reportview_response(
    data: Dict[str, Any],
    source: str,
    logger: Any,
) -> List[Dict[str, Any]]:
    """Convert reportview keys/values payload into a list of dictionaries."""
    message = data.get("message")
    if isinstance(message, list):
        if not message:
            return []
        logger.error(
            "Malformed timesheet reportview payload from %s: unexpected message list | payload=%s",
            source,
            format_payload_for_log(data),
        )
        raise TimesheetServiceError("Malformed timesheet response: invalid message list.")
    if not isinstance(message, dict):
        logger.error(
            "Malformed timesheet reportview payload from %s: missing message object | payload=%s",
            source,
            format_payload_for_log(data),
        )
        raise TimesheetServiceError("Malformed timesheet response: missing message object.")

    keys = message.get("keys")
    values = message.get("values")
    if not isinstance(keys, list) or not isinstance(values, list):
        logger.error(
            "Malformed timesheet reportview payload from %s: missing keys/values | payload=%s",
            source,
            format_payload_for_log(data),
        )
        raise TimesheetServiceError("Malformed timesheet response: missing message.keys or message.values.")

    timesheets: List[Dict[str, Any]] = []
    for raw_row in values:
        if not isinstance(raw_row, list):
            raise TimesheetServiceError("Malformed timesheet response: invalid row format.")
        timesheets.append(dict(zip(keys, raw_row)))
    return timesheets


def normalize_timesheet_detail_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert getdoc payload into a normalized timesheet detail dictionary."""
    docs = data.get("docs")
    if not isinstance(docs, list) or not docs:
        raise TimesheetServiceError("Malformed timesheet detail response: missing docs.")

    raw_doc = docs[0]
    if not isinstance(raw_doc, dict):
        raise TimesheetServiceError("Malformed timesheet detail response: invalid doc format.")

    raw_time_logs = raw_doc.get("time_logs") or []
    if not isinstance(raw_time_logs, list):
        raise TimesheetServiceError("Malformed timesheet detail response: invalid time_logs format.")

    return {
        "name": raw_doc.get("name"),
        "workflow_state": raw_doc.get("workflow_state"),
        "status": raw_doc.get("status"),
        "title": raw_doc.get("title"),
        "employee": raw_doc.get("employee"),
        "employee_name": raw_doc.get("employee_name"),
        "department": raw_doc.get("department"),
        "company": raw_doc.get("company"),
        "currency": raw_doc.get("currency"),
        "start_date": raw_doc.get("start_date"),
        "end_date": raw_doc.get("end_date"),
        "total_hours": raw_doc.get("total_hours"),
        "total_billable_hours": raw_doc.get("total_billable_hours"),
        "total_billable_amount": raw_doc.get("total_billable_amount"),
        "total_billed_amount": raw_doc.get("total_billed_amount"),
        "total_costing_amount": raw_doc.get("total_costing_amount"),
        "time_logs": [normalize_time_log_row(raw_log) for raw_log in raw_time_logs],
    }


def normalize_time_log_row(raw_log: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one time log row returned from getdoc."""
    if not isinstance(raw_log, dict):
        raise TimesheetServiceError("Malformed timesheet detail response: invalid time log row.")

    return {
        "name": raw_log.get("name"),
        "activity_type": raw_log.get("activity_type"),
        "project": raw_log.get("project"),
        "project_name": raw_log.get("project_name"),
        "description": raw_log.get("description"),
        "from_time": raw_log.get("from_time"),
        "to_time": raw_log.get("to_time"),
        "hours": raw_log.get("hours"),
        "is_billable": raw_log.get("is_billable"),
        "billing_hours": raw_log.get("billing_hours"),
        "billing_amount": raw_log.get("billing_amount"),
        "costing_amount": raw_log.get("costing_amount"),
    }


def format_payload_for_log(payload: Any) -> str:
    """Render a payload compactly for service-level diagnostics."""
    try:
        return json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        return str(payload)
