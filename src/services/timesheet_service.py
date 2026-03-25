import json
import logging
import time
import urllib.parse
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from src.api import ApiClient, ApiClientError
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class TimesheetServiceError(Exception):
    """Raised when a timesheet operation fails."""


class TimesheetService:
    """Loads timesheet list data from Frappe reportview."""

    _FIELDS = [
        "`tabTimesheet`.`workflow_state`",
        "`tabTimesheet`.`name`",
        "`tabTimesheet`.`owner`",
        "`tabTimesheet`.`creation`",
        "`tabTimesheet`.`modified`",
        "`tabTimesheet`.`modified_by`",
        "`tabTimesheet`.`_user_tags`",
        "`tabTimesheet`.`_comments`",
        "`tabTimesheet`.`_assign`",
        "`tabTimesheet`.`_liked_by`",
        "`tabTimesheet`.`docstatus`",
        "`tabTimesheet`.`idx`",
        "`tabTimesheet`.`status`",
        "`tabTimesheet`.`start_date`",
        "`tabTimesheet`.`total_billable_amount`",
        "`tabTimesheet`.`total_billed_amount`",
        "`tabTimesheet`.`total_costing_amount`",
        "`tabTimesheet`.`per_billed`",
        "`tabTimesheet`.`title`",
        "`tabTimesheet`.`total_hours`",
        "`tabTimesheet`.`end_date`",
        "`tabTimesheet`.`currency`",
    ]

    def __init__(self, api_client: ApiClient, auth_service: AuthService):
        """Store shared dependencies for authenticated timesheet fetching."""
        self.api_client = api_client
        self.auth_service = auth_service
        self.reportview_endpoint = "/api/method/frappe.desk.reportview.get"
        self.getdoc_endpoint = "/api/method/frappe.desk.form.load.getdoc"
        self.save_endpoint = "/api/method/frappe.desk.form.save.savedocs"

    def get_timesheets(
        self,
        start: int = 0,
        page_length: int = 20,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return normalized timesheet list records for one employee."""
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            raise TimesheetServiceError(
                "No authenticated user is available for the timesheet employee filter."
            )

        try:
            response = self.api_client.post(
                self.reportview_endpoint,
                data=urllib.parse.urlencode(
                    self._build_reportview_payload(
                        filters=[["Timesheet", "employee", "=", employee_filter]],
                        start=start,
                        page_length=page_length,
                    )
                ),
                headers=self._build_headers(
                    doctype="Timesheet",
                    csrf_token=csrf_token,
                    include_form_content_type=True,
                ),
            )
            return self._normalize_reportview_response(
                response.json(),
                source="get_timesheets",
            )
        except ApiClientError as exc:
            logger.error("Failed to fetch timesheets: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch timesheets: {exc}") from exc

    def get_latest_timesheet_for_user(
        self,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent timesheet detail for the current user."""
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            raise TimesheetServiceError(
                "No authenticated user is available for the timesheet employee filter."
            )

        try:
            timesheets = self._fetch_timesheet_summaries(
                filters=[["Timesheet", "employee", "=", employee_filter]],
                start=0,
                page_length=1,
                csrf_token=csrf_token,
                source="get_latest_timesheet_for_user",
            )
            if not timesheets:
                return None
            return self.get_timesheet_detail(timesheets[0]["name"], csrf_token=csrf_token)
        except ApiClientError as exc:
            logger.error("Failed to fetch latest timesheet: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch latest timesheet: {exc}") from exc

    def get_latest_smart_log_state(
        self,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest row state used to prefill and merge smart logs."""
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            raise TimesheetServiceError(
                "No authenticated user is available for the timesheet employee filter."
            )

        try:
            latest_doc = self._get_latest_raw_timesheet_doc(employee_filter, csrf_token=csrf_token)
            if not latest_doc:
                return None

            last_row = self._get_last_time_log(latest_doc.get("time_logs"))
            if not last_row:
                return None

            return {
                "timesheet_name": latest_doc.get("name"),
                "row_name": last_row.get("name"),
                "project_id": last_row.get("project"),
                "project_name": last_row.get("project_name"),
                "activity_name": last_row.get("activity_type") or "",
                "description": last_row.get("description") or "",
                "is_billable": bool(last_row.get("is_billable")),
                "timestamp": last_row.get("to_time") or last_row.get("from_time"),
            }
        except ApiClientError as exc:
            logger.error("Failed to fetch latest smart-log state: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch latest smart-log state: {exc}") from exc

    def save_timesheet_log(
        self,
        project_id: str,
        project_name: str,
        activity: str,
        description: str,
        is_billable: bool,
        interval_seconds: int,
        saved_at: Optional[Any] = None,
        csrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save one smart-log submission into today's timesheet."""
        if not project_id or not project_name or not activity or not description:
            raise TimesheetServiceError("Timesheet save requires project, activity, and description.")
        if interval_seconds <= 0:
            raise TimesheetServiceError("Timesheet save requires a positive smart-log interval.")

        employee = self.auth_service.getSession()
        if not employee:
            raise TimesheetServiceError(
                "No authenticated user is available for the timesheet employee filter."
            )

        try:
            current_dt = self._coerce_datetime(saved_at)
            previous_state = self.get_latest_smart_log_state(employee=employee, csrf_token=csrf_token)
            timesheet_doc, is_new_doc = self._get_or_prepare_timesheet_for_day(
                day=current_dt.date(),
                employee=employee,
                csrf_token=csrf_token,
            )
            timesheet_doc = self._apply_smart_log_update_to_doc(
                timesheet_doc=timesheet_doc,
                previous_state=previous_state,
                project_id=project_id,
                project_name=project_name,
                activity=activity,
                description=description,
                is_billable=is_billable,
                interval_seconds=interval_seconds,
                current_dt=current_dt,
                employee=employee,
                is_new_doc=is_new_doc,
            )

            try:
                response = self._post_timesheet_doc(timesheet_doc, csrf_token=csrf_token)
            except ApiClientError as exc:
                if not is_new_doc and exc.exc_type == "TimestampMismatchError":
                    logger.warning(
                        "Timestamp mismatch while saving %s; refetching latest doc and retrying once.",
                        timesheet_doc.get("name"),
                    )
                    refreshed_doc = self._get_raw_timesheet_doc(
                        str(timesheet_doc["name"]),
                        csrf_token=csrf_token,
                    )
                    refreshed_state = self._build_smart_log_state_from_doc(refreshed_doc)
                    retry_doc = self._apply_smart_log_update_to_doc(
                        timesheet_doc=refreshed_doc,
                        previous_state=refreshed_state,
                        project_id=project_id,
                        project_name=project_name,
                        activity=activity,
                        description=description,
                        is_billable=is_billable,
                        interval_seconds=interval_seconds,
                        current_dt=current_dt,
                        employee=employee,
                        is_new_doc=False,
                    )
                    response = self._post_timesheet_doc(retry_doc, csrf_token=csrf_token)
                else:
                    raise
            return self._normalize_timesheet_detail_response(response.json())
        except ApiClientError as exc:
            logger.error("Failed to save timesheet log: %s", exc)
            raise TimesheetServiceError(f"Failed to save timesheet log: {exc}") from exc

    def get_timesheet_detail(
        self,
        name: str,
        csrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return one normalized timesheet detail payload."""
        if not name:
            raise TimesheetServiceError("Timesheet detail requires a valid timesheet name.")

        params = {
            "doctype": "Timesheet",
            "name": name,
            "_": int(time.time() * 1000),
        }

        try:
            response = self.api_client.get(
                self.getdoc_endpoint,
                params=params,
                headers=self._build_headers(doctype="Timesheet", csrf_token=csrf_token),
            )
            return self._normalize_timesheet_detail_response(response.json())
        except ApiClientError as exc:
            logger.error("Failed to fetch timesheet detail: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch timesheet detail: {exc}") from exc

    def _normalize_reportview_response(
        self,
        data: Dict[str, Any],
        source: str = "reportview",
    ) -> List[Dict[str, Any]]:
        """Convert reportview keys/values payload into a list of dictionaries."""
        message = data.get("message")
        if isinstance(message, list):
            if not message:
                return []
            logger.error(
                "Malformed timesheet reportview payload from %s: unexpected message list | payload=%s",
                source,
                self._format_payload_for_log(data),
            )
            raise TimesheetServiceError("Malformed timesheet response: invalid message list.")
        if not isinstance(message, dict):
            logger.error(
                "Malformed timesheet reportview payload from %s: missing message object | payload=%s",
                source,
                self._format_payload_for_log(data),
            )
            raise TimesheetServiceError("Malformed timesheet response: missing message object.")

        keys = message.get("keys")
        values = message.get("values")
        if not isinstance(keys, list) or not isinstance(values, list):
            logger.error(
                "Malformed timesheet reportview payload from %s: missing keys/values | payload=%s",
                source,
                self._format_payload_for_log(data),
            )
            raise TimesheetServiceError(
                "Malformed timesheet response: missing message.keys or message.values."
            )

        timesheets: List[Dict[str, Any]] = []
        for raw_row in values:
            if not isinstance(raw_row, list):
                raise TimesheetServiceError("Malformed timesheet response: invalid row format.")
            timesheets.append(dict(zip(keys, raw_row)))
        return timesheets

    def _normalize_timesheet_detail_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert getdoc payload into a normalized timesheet detail dictionary."""
        docs = data.get("docs")
        if not isinstance(docs, list) or not docs:
            raise TimesheetServiceError("Malformed timesheet detail response: missing docs.")

        raw_doc = docs[0]
        if not isinstance(raw_doc, dict):
            raise TimesheetServiceError("Malformed timesheet detail response: invalid doc format.")

        raw_time_logs = raw_doc.get("time_logs") or []
        if not isinstance(raw_time_logs, list):
            raise TimesheetServiceError(
                "Malformed timesheet detail response: invalid time_logs format."
            )

        time_logs: List[Dict[str, Any]] = []
        for raw_log in raw_time_logs:
            if not isinstance(raw_log, dict):
                raise TimesheetServiceError(
                    "Malformed timesheet detail response: invalid time log row."
                )
            time_logs.append(
                {
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
            )

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
            "time_logs": time_logs,
        }

    def _fetch_timesheet_summaries(
        self,
        filters: List[List[Any]],
        start: int,
        page_length: int,
        csrf_token: Optional[str] = None,
        source: str = "reportview",
    ) -> List[Dict[str, Any]]:
        """Fetch reportview rows for Timesheet using explicit filters."""
        response = self.api_client.post(
            self.reportview_endpoint,
            data=urllib.parse.urlencode(
                self._build_reportview_payload(
                    filters=filters,
                    start=start,
                    page_length=page_length,
                )
            ),
            headers=self._build_headers(
                doctype="Timesheet",
                csrf_token=csrf_token,
                include_form_content_type=True,
            ),
        )
        return self._normalize_reportview_response(response.json(), source=source)

    def _build_reportview_payload(
        self,
        filters: List[List[Any]],
        start: int,
        page_length: int,
    ) -> Dict[str, Any]:
        """Build a reportview payload for list queries."""
        return {
            "doctype": "Timesheet",
            "fields": json.dumps(self._FIELDS),
            "filters": json.dumps(filters),
            "order_by": "`tabTimesheet`.`start_date` desc",
            "start": start,
            "page_length": page_length,
            "view": "List",
            "group_by": "",
            "with_comment_count": 1,
            "_": int(time.time() * 1000),
        }

    def _get_raw_timesheet_doc(
        self,
        name: str,
        csrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch and return the raw Timesheet doc from getdoc."""
        if not name:
            raise TimesheetServiceError("Timesheet detail requires a valid timesheet name.")

        response = self.api_client.get(
            self.getdoc_endpoint,
            params={
                "doctype": "Timesheet",
                "name": name,
                "_": int(time.time() * 1000),
            },
            headers=self._build_headers(doctype="Timesheet", csrf_token=csrf_token),
        )
        docs = response.json().get("docs")
        if not isinstance(docs, list) or not docs or not isinstance(docs[0], dict):
            raise TimesheetServiceError("Malformed timesheet detail response: missing docs.")
        return docs[0]

    def _get_latest_raw_timesheet_doc(
        self,
        employee: str,
        csrf_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the raw latest timesheet doc for one employee."""
        summaries = self._fetch_timesheet_summaries(
            filters=[["Timesheet", "employee", "=", employee]],
            start=0,
            page_length=1,
            csrf_token=csrf_token,
            source="_get_latest_raw_timesheet_doc",
        )
        if not summaries:
            return None
        return self._get_raw_timesheet_doc(summaries[0]["name"], csrf_token=csrf_token)

    def _build_smart_log_state_from_doc(
        self,
        raw_doc: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Build smart-log defaults/merge state from one raw timesheet doc."""
        if not isinstance(raw_doc, dict):
            return None

        last_row = self._get_last_time_log(raw_doc.get("time_logs"))
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

    def _get_or_prepare_timesheet_for_day(
        self,
        day: date,
        employee: str,
        csrf_token: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        """Return today's timesheet doc or a new seeded draft doc when missing."""
        day_str = day.isoformat()
        todays = self._fetch_timesheet_summaries(
            filters=[
                ["Timesheet", "employee", "=", employee],
                ["Timesheet", "start_date", "=", day_str],
            ],
            start=0,
            page_length=1,
            csrf_token=csrf_token,
            source="_get_or_prepare_timesheet_for_day",
        )
        if todays:
            return self._get_raw_timesheet_doc(todays[0]["name"], csrf_token=csrf_token), False

        latest = self._get_latest_raw_timesheet_doc(employee, csrf_token=csrf_token)
        if latest is None:
            raise TimesheetServiceError(
                "No existing timesheet is available to seed a new timesheet for today."
            )
        return self._build_new_timesheet_doc(latest, day), True

    def _build_new_timesheet_doc(self, template: Dict[str, Any], day: date) -> Dict[str, Any]:
        """Create a new unsaved timesheet doc by seeding stable fields from a template."""
        current_dt = datetime.now()
        day_str = day.isoformat()
        doc = deepcopy(template)
        doc.update(
            {
                "name": f"new-timesheet-{int(time.time() * 1000)}",
                "creation": self._format_doc_datetime(current_dt, include_microseconds=True),
                "modified": self._format_doc_datetime(current_dt, include_microseconds=True),
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

    def _apply_smart_log_update_to_doc(
        self,
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
        previous_dt = self._coerce_optional_datetime(previous_state.get("timestamp") if previous_state else None)
        same_day_previous = previous_dt is not None and previous_dt.date() == current_dt.date()
        interval_hours = round(interval_seconds / 3600, 6)
        should_merge = (
            previous_state is not None
            and previous_state.get("timesheet_name") == timesheet_doc.get("name")
            and previous_state.get("project_id") == project_id
            and previous_state.get("activity_name") == activity
            and previous_state.get("description") == description
            and bool(previous_state.get("is_billable")) == is_billable
        )

        time_logs = list(timesheet_doc.get("time_logs") or [])
        if should_merge:
            target_row = self._find_time_log_by_name(time_logs, previous_state.get("row_name"))
            if target_row is None:
                raise TimesheetServiceError("Could not find the previous timesheet row to update.")

            start_dt = self._coerce_optional_datetime(target_row.get("from_time"))
            previous_to_dt = self._coerce_optional_datetime(target_row.get("to_time"))
            if start_dt and previous_to_dt and previous_to_dt < start_dt:
                raise TimesheetServiceError("Existing timesheet row has invalid time boundaries.")

            target_row["project"] = project_id
            target_row["project_name"] = project_name
            target_row["activity_type"] = activity
            target_row["description"] = description
            target_row["is_billable"] = 1 if is_billable else 0
            next_to_dt = current_dt
            if previous_to_dt and next_to_dt < previous_to_dt:
                raise TimesheetServiceError("New smart-log time cannot be earlier than the existing row end time.")
            target_row["to_time"] = self._format_doc_datetime(next_to_dt)
            target_row["modified"] = self._format_doc_datetime(current_dt, include_microseconds=True)
            target_row["modified_by"] = employee

            hours = self._compute_hours(start_dt, next_to_dt) if start_dt else interval_hours
            target_row["hours"] = hours
            target_row["billing_hours"] = hours if is_billable else 0.0
        else:
            if same_day_previous:
                to_dt = current_dt
                from_dt = previous_dt
                if from_dt and to_dt < from_dt:
                    raise TimesheetServiceError("New smart-log time cannot be earlier than the previous row end time.")
                hours = self._compute_hours(from_dt, to_dt) if from_dt else interval_hours
            else:
                to_dt = current_dt
                from_dt = to_dt - self._interval_delta(interval_seconds)
                hours = interval_hours
            time_logs.append(
                self._build_time_log_row(
                    parent_name=timesheet_doc["name"],
                    current_dt=to_dt,
                    from_dt=from_dt,
                    hours=hours,
                    project_id=project_id,
                    project_name=project_name,
                    activity=activity,
                    description=description,
                    is_billable=is_billable,
                    idx=len(time_logs) + 1,
                    owner=timesheet_doc.get("owner") or employee,
                )
            )
            timesheet_doc["time_logs"] = time_logs

        self._recompute_timesheet_totals(timesheet_doc)
        timesheet_doc["__unsaved"] = 1
        timesheet_doc["modified_by"] = employee
        if is_new_doc:
            timesheet_doc["__islocal"] = 1
            timesheet_doc["modified"] = self._format_doc_datetime(current_dt, include_microseconds=True)

        return timesheet_doc

    def _post_timesheet_doc(
        self,
        timesheet_doc: Dict[str, Any],
        csrf_token: Optional[str] = None,
    ):
        """Persist one raw timesheet doc through frappe.savedocs."""
        return self.api_client.post(
            self.save_endpoint,
            data=urllib.parse.urlencode(
                {
                    "doc": json.dumps(timesheet_doc),
                    "action": "Save",
                }
            ),
            headers=self._build_headers(
                doctype="Timesheet",
                csrf_token=csrf_token,
                include_form_content_type=True,
                include_doctype_header=False,
            ),
        )

    def _build_time_log_row(
        self,
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
        formatted_current = self._format_doc_datetime(current_dt, include_microseconds=True)
        return {
            "name": f"new-time-log-{int(time.time() * 1000)}",
            "owner": owner,
            "creation": formatted_current,
            "modified": formatted_current,
            "modified_by": owner,
            "docstatus": 0,
            "idx": idx,
            "activity_type": activity,
            "from_time": self._format_doc_datetime(from_dt),
            "description": description,
            "expected_hours": 0,
            "to_time": self._format_doc_datetime(current_dt),
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

    def _recompute_timesheet_totals(self, timesheet_doc: Dict[str, Any]) -> None:
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

    def _get_last_time_log(self, raw_time_logs: Any) -> Optional[Dict[str, Any]]:
        """Return the latest time log row from a raw timesheet doc."""
        if not isinstance(raw_time_logs, list) or not raw_time_logs:
            return None

        valid_rows = [row for row in raw_time_logs if isinstance(row, dict)]
        if not valid_rows:
            return None
        valid_rows.sort(
            key=lambda row: row.get("to_time") or row.get("from_time") or "",
        )
        return valid_rows[-1]

    def _find_time_log_by_name(
        self,
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

    def _coerce_datetime(self, value: Optional[Any]) -> datetime:
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

    def _coerce_optional_datetime(self, value: Optional[Any]) -> Optional[datetime]:
        """Convert an optional date/time string into a datetime."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise TimesheetServiceError(f"Invalid timesheet datetime value: {value}") from exc
        raise TimesheetServiceError(f"Unsupported timesheet datetime type: {type(value).__name__}")

    def _interval_delta(self, interval_seconds: int):
        """Return a timedelta for the configured smart-log interval."""
        from datetime import timedelta

        return timedelta(seconds=interval_seconds)

    def _compute_hours(self, from_dt: datetime, to_dt: datetime) -> float:
        """Return non-negative elapsed hours between two datetimes."""
        delta_seconds = (to_dt - from_dt).total_seconds()
        if delta_seconds <= 0:
            return 0.0
        return round(delta_seconds / 3600, 6)

    def _format_doc_datetime(
        self,
        value: datetime,
        include_microseconds: bool = False,
    ) -> str:
        """Format datetimes the way Frappe docs expect."""
        if include_microseconds:
            return value.strftime("%Y-%m-%d %H:%M:%S.%f")
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _build_headers(
        self,
        doctype: str,
        csrf_token: Optional[str] = None,
        include_form_content_type: bool = False,
        include_doctype_header: bool = True,
    ) -> Dict[str, str]:
        """Build shared Frappe headers for timesheet requests."""
        headers = {
            "accept": "application/json",
            "x-frappe-cmd": "",
            "x-requested-with": "XMLHttpRequest",
        }
        if include_doctype_header:
            headers["x-frappe-doctype"] = doctype
        if include_form_content_type:
            headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        csrf_header = csrf_token or self.api_client.get_cookies().get("csrf_token")
        if csrf_header:
            headers["x-frappe-csrf-token"] = csrf_header
        return headers

    def _format_payload_for_log(self, payload: Any) -> str:
        """Render a payload compactly for service-level diagnostics."""
        try:
            return json.dumps(payload, sort_keys=True, default=str)
        except TypeError:
            return str(payload)
