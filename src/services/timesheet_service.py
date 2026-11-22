import json
import logging
import time
import urllib.parse
from datetime import date
from typing import Any, Dict, List, Optional

from src.api import ApiClient, ApiClientError
from src.services.auth_service import AuthService
from src.services.timesheet_parsing import (
    format_payload_for_log,
    normalize_reportview_response,
    normalize_timesheet_detail_response,
)
from src.services.timesheet_edit import (
    apply_time_log_changes,
    ensure_editable,
    remove_time_log,
)
from src.services.timesheet_shared import TimesheetAuthError, TimesheetServiceError
from src.services.timesheet_smart_log import (
    apply_smart_log_update_to_doc,
    build_new_timesheet_doc,
    build_smart_log_state_from_doc,
    coerce_datetime,
    find_time_log_by_name,
    is_placeholder_time_log,
    should_merge_with_previous,
)

logger = logging.getLogger(__name__)


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
        "`tabTimesheet`.`employee`",
        "`tabTimesheet`.`employee_name`",
    ]

    def __init__(self, api_client: ApiClient, auth_service: AuthService):
        """Store shared dependencies for authenticated timesheet fetching."""
        self.api_client = api_client
        self.auth_service = auth_service
        self.reportview_endpoint = "/api/method/frappe.desk.reportview.get"
        self.getdoc_endpoint = "/api/method/frappe.desk.form.load.getdoc"
        self.save_endpoint = "/api/method/frappe.desk.form.save.savedocs"
        self.transitions_endpoint = "/api/method/frappe.model.workflow.get_transitions"
        self.apply_workflow_endpoint = "/api/method/frappe.model.workflow.apply_workflow"

    # Public service API
    def get_timesheets(
        self,
        start: int = 0,
        page_length: int = 20,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
        status: Optional[str] = None,
        workflow_state: Optional[str] = None,
        from_date: Optional[Any] = None,
        to_date: Optional[Any] = None,
        covering_date: Optional[Any] = None,
        all_employees: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return normalized timesheet list records for one employee (default: you).

        With `all_employees=True` and no `employee`, return everyone's timesheets the
        server lets this account see (the server enforces permissions).

        Optional filters: exact `status` / `workflow_state`; `from_date` keeps
        timesheets starting on or after it; `to_date` keeps those ending on or
        before it; `covering_date` keeps the timesheet whose range contains it.
        """
        employee_filters: List[List[Any]] = []
        if employee or not all_employees:
            employee_filter = employee or self.auth_service.getSession()
            if not employee_filter:
                raise TimesheetAuthError(
                    "No authenticated user is available for the timesheet employee filter."
                )
            employee_filters.append(["Timesheet", "employee", "=", employee_filter])

        try:
            response = self.api_client.post(
                self.reportview_endpoint,
                data=urllib.parse.urlencode(
                    self._build_reportview_payload(
                        filters=employee_filters
                        + self._build_optional_filters(
                            status, workflow_state, from_date, to_date, covering_date
                        ),
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
            rows = self._normalize_reportview_response(
                response.json(),
                source="get_timesheets",
            )
            for row in rows:  # the server pads some names with double spaces
                if isinstance(row.get("employee_name"), str):
                    row["employee_name"] = " ".join(row["employee_name"].split())
            return rows
        except ApiClientError as exc:
            logger.error("Failed to fetch timesheets: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch timesheets: {exc}") from exc

    @staticmethod
    def _build_optional_filters(
        status: Optional[str],
        workflow_state: Optional[str],
        from_date: Optional[Any],
        to_date: Optional[Any],
        covering_date: Optional[Any],
    ) -> List[List[Any]]:
        """Translate list filters into reportview filter triples."""
        extra: List[List[Any]] = []
        if status:
            extra.append(["Timesheet", "status", "=", status])
        if workflow_state:
            extra.append(["Timesheet", "workflow_state", "=", workflow_state])
        if from_date:
            extra.append(["Timesheet", "start_date", ">=", str(from_date)])
        if to_date:
            extra.append(["Timesheet", "end_date", "<=", str(to_date)])
        if covering_date:
            extra.append(["Timesheet", "start_date", "<=", str(covering_date)])
            extra.append(["Timesheet", "end_date", ">=", str(covering_date)])
        return extra

    def get_latest_timesheet_for_user(
        self,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent timesheet detail for the current user."""
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            raise TimesheetAuthError(
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
            raise TimesheetAuthError(
                "No authenticated user is available for the timesheet employee filter."
            )

        try:
            latest_doc = self._get_latest_raw_timesheet_doc(employee_filter, csrf_token=csrf_token)
            if not latest_doc:
                return None

            return self._build_smart_log_state_from_doc(latest_doc)
        except ApiClientError as exc:
            logger.error("Failed to fetch latest smart-log state: %s", exc)
            raise TimesheetServiceError(f"Failed to fetch latest smart-log state: {exc}") from exc

    def get_recent_smart_log_options(
        self,
        limit: int = 5,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return a list of unique recent project/activity pairs for UI history."""
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            return []

        try:
            # Fetch the latest 3 timesheet summaries to ensure we have enough history
            summaries = self._fetch_timesheet_summaries(
                filters=[["Timesheet", "employee", "=", employee_filter]],
                start=0,
                page_length=3,
                csrf_token=csrf_token,
                source="get_recent_smart_log_options",
            )
            
            recent_options = []
            seen_pairs = set()

            for summary in summaries:
                doc = self._get_raw_timesheet_doc(summary["name"], csrf_token=csrf_token)
                time_logs = doc.get("time_logs") or []
                
                # Sort logs by time (descending) to get the most recent first
                sorted_logs = sorted(
                    time_logs,
                    key=lambda x: x.get("to_time") or x.get("from_time") or "",
                    reverse=True
                )

                for log in sorted_logs:
                    project_id = log.get("project")
                    project_name = log.get("project_name")
                    activity = log.get("activity_type")
                    
                    if not project_id or not project_name or not activity:
                        continue
                        
                    pair = (project_id, activity)
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        recent_options.append({
                            "project_id": str(project_id),
                            "project_name": str(project_name),
                            "activity_name": str(activity),
                            "is_billable": bool(log.get("is_billable")),
                            "description": str(log.get("description") or ""),
                        })
                        
                        if len(recent_options) >= limit:
                            return recent_options
                            
            return recent_options
        except Exception as exc:
            logger.error("Failed to fetch recent smart-log options: %s", exc)
            return []

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
        if interval_seconds < 0:
            raise TimesheetServiceError("Timesheet save requires a non-negative smart-log interval.")

        employee = self.auth_service.getSession()
        if not employee:
            raise TimesheetAuthError(
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
            save_debug_context = self._build_smart_log_save_debug_context(
                timesheet_doc=timesheet_doc,
                previous_state=previous_state,
                project_id=project_id,
                activity=activity,
                description=description,
                is_billable=is_billable,
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
                    save_debug_context = self._build_smart_log_save_debug_context(
                        timesheet_doc=retry_doc,
                        previous_state=refreshed_state,
                        project_id=project_id,
                        activity=activity,
                        description=description,
                        is_billable=is_billable,
                    )
                    response = self._post_timesheet_doc(retry_doc, csrf_token=csrf_token)
                else:
                    self._log_overlap_debug_context(exc, save_debug_context)
                    raise
            return self._normalize_timesheet_detail_response(response.json())
        except ApiClientError as exc:
            self._log_overlap_debug_context(exc, save_debug_context if "save_debug_context" in locals() else None)
            logger.error("Failed to save timesheet log: %s", exc)
            raise TimesheetServiceError(f"Failed to save timesheet log: {exc}") from exc

    # ── changing existing timesheets ──────────────────────────────────────
    def _modify_timesheet(self, name: str, mutate, csrf_token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a timesheet, apply `mutate(doc, employee)`, save it (retrying once on a stale copy)."""
        employee = self.auth_service.getSession()
        if not employee:
            raise TimesheetAuthError("No authenticated user is available for the timesheet employee filter.")
        for attempt in (1, 2):
            doc = self._get_raw_timesheet_doc(name, csrf_token=csrf_token)
            mutate(doc, employee)
            try:
                response = self._post_timesheet_doc(doc, csrf_token=csrf_token)
                return self._normalize_timesheet_detail_response(response.json())
            except ApiClientError as exc:
                if attempt == 1 and exc.exc_type == "TimestampMismatchError":
                    logger.warning("Timestamp mismatch while changing %s; refetching and retrying once.", name)
                    continue
                logger.error("Failed to update timesheet %s: %s", name, exc)
                raise TimesheetServiceError(f"Failed to update timesheet: {exc}") from exc
        raise TimesheetServiceError("Failed to update timesheet.")  # pragma: no cover

    def update_time_log(
        self,
        timesheet_name: str,
        row_name: str,
        csrf_token: Optional[str] = None,
        **changes: Any,
    ) -> Dict[str, Any]:
        """Change one time-log row. Keyword changes: description, activity, project_id,
        project_name, is_billable, from_time, to_time (datetimes)."""
        if not timesheet_name or not row_name:
            raise TimesheetServiceError("Updating a time log needs a timesheet and a row.")
        return self._modify_timesheet(
            timesheet_name,
            lambda doc, employee: apply_time_log_changes(doc, row_name, employee, **changes),
            csrf_token=csrf_token,
        )

    def delete_time_log(self, timesheet_name: str, row_name: str, csrf_token: Optional[str] = None) -> Dict[str, Any]:
        """Remove one time-log row from a Pending draft."""
        if not timesheet_name or not row_name:
            raise TimesheetServiceError("Deleting a time log needs a timesheet and a row.")
        return self._modify_timesheet(
            timesheet_name,
            lambda doc, employee: remove_time_log(doc, row_name, employee),
            csrf_token=csrf_token,
        )

    def get_workflow_actions(self, name: str, csrf_token: Optional[str] = None) -> List[str]:
        """Return the workflow actions (e.g. ["Submit"]) the current user may apply."""
        try:
            doc = self._get_raw_timesheet_doc(name, csrf_token=csrf_token)
            response = self.api_client.post(
                self.transitions_endpoint,
                data=urllib.parse.urlencode({"doc": json.dumps(doc)}),
                headers=self._build_headers(doctype="Timesheet", csrf_token=csrf_token, include_form_content_type=True),
            )
        except ApiClientError as exc:
            raise TimesheetServiceError(f"Failed to read the workflow actions: {exc}") from exc
        message = response.json().get("message") or []
        return [str(t.get("action")) for t in message if isinstance(t, dict) and t.get("action")]

    def submit_timesheet(self, name: str, csrf_token: Optional[str] = None) -> Dict[str, Any]:
        """Apply the workflow's "Submit" action to a Pending draft."""
        if not name:
            raise TimesheetServiceError("Submitting needs a timesheet name.")
        doc = self._get_raw_timesheet_doc(name, csrf_token=csrf_token)
        ensure_editable(doc)
        if not doc.get("time_logs"):
            raise TimesheetServiceError(f"{name} has no time logs to submit.")
        actions = self.get_workflow_actions(name, csrf_token=csrf_token)
        if "Submit" not in actions:
            available = ", ".join(actions) or "none"
            raise TimesheetServiceError(f"{name} cannot be submitted by you right now (available actions: {available}).")
        try:
            response = self.api_client.post(
                self.apply_workflow_endpoint,
                data=urllib.parse.urlencode({"doc": json.dumps(doc), "action": "Submit"}),
                headers=self._build_headers(doctype="Timesheet", csrf_token=csrf_token, include_form_content_type=True),
            )
        except ApiClientError as exc:
            logger.error("Failed to submit timesheet %s: %s", name, exc)
            raise TimesheetServiceError(f"Failed to submit timesheet: {exc}") from exc
        updated = response.json().get("message")
        return self._normalize_timesheet_detail_response({"docs": [updated]}) if isinstance(updated, dict) else self.get_timesheet_detail(name)

    def delete_timesheet(self, name: str, csrf_token: Optional[str] = None) -> None:
        """Delete a whole Pending draft timesheet."""
        if not name:
            raise TimesheetServiceError("Deleting needs a timesheet name.")
        ensure_editable(self._get_raw_timesheet_doc(name, csrf_token=csrf_token))
        try:
            self.api_client.delete(f"/api/resource/Timesheet/{urllib.parse.quote(name, safe='')}")
        except ApiClientError as exc:
            logger.error("Failed to delete timesheet %s: %s", name, exc)
            raise TimesheetServiceError(f"Failed to delete timesheet: {exc}") from exc

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

    # Response normalization and transport helpers
    def _normalize_reportview_response(
        self,
        data: Dict[str, Any],
        source: str = "reportview",
    ) -> List[Dict[str, Any]]:
        return normalize_reportview_response(data=data, source=source, logger=logger)

    def _normalize_timesheet_detail_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_timesheet_detail_response(data)

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

    # Smart-log state and mutation helpers
    def _build_smart_log_state_from_doc(
        self,
        raw_doc: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        return build_smart_log_state_from_doc(raw_doc)

    def _get_or_prepare_timesheet_for_day(
        self,
        day: date,
        employee: str,
        csrf_token: Optional[str] = None,
    ) -> tuple[Dict[str, Any], bool]:
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
        return build_new_timesheet_doc(template, day)

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
        current_dt,
        employee: str,
        is_new_doc: bool,
    ) -> Dict[str, Any]:
        return apply_smart_log_update_to_doc(
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

    def _build_smart_log_save_debug_context(
        self,
        timesheet_doc: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]],
        project_id: str,
        activity: str,
        description: str,
        is_billable: bool,
    ) -> Dict[str, Any]:
        """Return compact diagnostics about the row being persisted."""
        merge_expected = should_merge_with_previous(
            previous_state=previous_state,
            timesheet_name=timesheet_doc.get("name"),
            project_id=project_id,
            activity=activity,
            description=description,
            is_billable=is_billable,
        )
        target_row = None
        if merge_expected and previous_state:
            target_row = find_time_log_by_name(
                timesheet_doc.get("time_logs") or [],
                previous_state.get("row_name"),
            )
        if target_row is None:
            time_logs = timesheet_doc.get("time_logs") or []
            if time_logs:
                target_row = time_logs[-1]

        mode = "merge"
        if target_row is not None and is_placeholder_time_log(target_row):
            mode = "placeholder"
        elif not merge_expected:
            mode = "append"

        return {
            "mode": mode,
            "timesheet_name": timesheet_doc.get("name"),
            "row_name": target_row.get("name") if isinstance(target_row, dict) else None,
            "from_time": target_row.get("from_time") if isinstance(target_row, dict) else None,
            "to_time": target_row.get("to_time") if isinstance(target_row, dict) else None,
        }

    def _log_overlap_debug_context(
        self,
        exc: ApiClientError,
        debug_context: Optional[Dict[str, Any]],
    ) -> None:
        """Log extra context when the server rejects a row for overlap."""
        if exc.exc_type != "OverlapError" or not debug_context:
            return

        logger.error(
            "OverlapError while saving smart log: mode=%s timesheet=%s row=%s window=%s -> %s",
            debug_context.get("mode"),
            debug_context.get("timesheet_name"),
            debug_context.get("row_name"),
            debug_context.get("from_time"),
            debug_context.get("to_time"),
        )

    # Date/time and request formatting helpers
    def _coerce_datetime(self, value: Optional[Any]):
        return coerce_datetime(value)

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
        return format_payload_for_log(payload)
