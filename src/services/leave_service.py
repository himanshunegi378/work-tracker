import json
import logging
import time
import urllib.parse
from datetime import date
from typing import Any, Dict, List, Optional

from src.api import ApiClient, ApiClientError
from src.services.auth_service import AuthService
from src.services.timesheet_shared import TimesheetAuthError

logger = logging.getLogger(__name__)

DOCTYPE = "Leave Application"


class LeaveServiceError(Exception):
    """Raised when a leave operation fails."""


class LeaveAuthError(LeaveServiceError, TimesheetAuthError):
    """No logged-in user (also an AuthenticationRequiredError so the CLI shows the login hint)."""

    def __init__(self, message: str):
        TimesheetAuthError.__init__(self, message)


class LeaveService:
    """Loads the user's leave applications from Frappe reportview."""

    _COLUMNS = [
        "name", "employee", "employee_name", "leave_type", "from_date", "to_date",
        "total_leave_days", "status", "docstatus", "creation", "modified",
    ]

    _BALANCE_KEYS = (
        "total_leaves", "leaves_taken", "leaves_pending_approval", "expired_leaves", "remaining_leaves",
    )

    def __init__(self, api_client: ApiClient, auth_service: AuthService):
        self.api_client = api_client
        self.auth_service = auth_service
        self.reportview_endpoint = "/api/method/frappe.desk.reportview.get"
        self.leave_details_endpoint = (
            "/api/method/hrms.hr.doctype.leave_application.leave_application.get_leave_details"
        )

    def get_leave_applications(
        self,
        start: int = 0,
        page_length: int = 20,
        employee: Optional[str] = None,
        status: Optional[str] = None,
        leave_type: Optional[str] = None,
        from_date: Optional[Any] = None,
        to_date: Optional[Any] = None,
        csrf_token: Optional[str] = None,
        all_employees: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return leave applications for one employee (default: you), newest first.

        With `all_employees=True` and no `employee`, return everyone's leaves that the
        server lets this account see (the server enforces permissions).

        `from_date` keeps leaves ending on or after it; `to_date` keeps leaves
        starting on or before it (so a leave overlapping the range is included).
        """
        filters: List[List[Any]] = []
        if employee or not all_employees:
            employee_filter = employee or self.auth_service.getSession()
            if not employee_filter:
                raise LeaveAuthError("No authenticated user is available for the leave employee filter.")
            filters.append([DOCTYPE, "employee", "=", employee_filter])
        if status:
            filters.append([DOCTYPE, "status", "=", status])
        if leave_type:
            filters.append([DOCTYPE, "leave_type", "=", leave_type])
        if from_date:
            filters.append([DOCTYPE, "to_date", ">=", str(from_date)])
        if to_date:
            filters.append([DOCTYPE, "from_date", "<=", str(to_date)])

        payload = {
            "doctype": DOCTYPE,
            "fields": json.dumps([f"`tab{DOCTYPE}`.`{c}`" for c in self._COLUMNS]),
            "filters": json.dumps(filters),
            "order_by": f"`tab{DOCTYPE}`.`modified` desc",
            "start": start,
            "page_length": page_length,
            "view": "List",
            "group_by": "",
            "with_comment_count": 1,
            "_": int(time.time() * 1000),
        }
        headers = {
            "accept": "application/json",
            "x-frappe-cmd": "",
            "x-requested-with": "XMLHttpRequest",
            "x-frappe-doctype": DOCTYPE,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        csrf = csrf_token or self.api_client.get_cookies().get("csrf_token")
        if csrf:
            headers["x-frappe-csrf-token"] = csrf

        try:
            response = self.api_client.post(
                self.reportview_endpoint, data=urllib.parse.urlencode(payload), headers=headers
            )
        except ApiClientError as exc:
            logger.error("Failed to fetch leave applications: %s", exc)
            raise LeaveServiceError(f"Failed to fetch leave applications: {exc}") from exc
        return self._normalize(response.json())

    def get_leave_types(self, csrf_token: Optional[str] = None) -> List[str]:
        """Return the leave type names configured on the server (for filter dropdowns)."""
        headers = {"accept": "application/json", "x-requested-with": "XMLHttpRequest"}
        csrf = csrf_token or self.api_client.get_cookies().get("csrf_token")
        if csrf:
            headers["x-frappe-csrf-token"] = csrf
        try:
            response = self.api_client.get(
                "/api/method/frappe.client.get_list",
                params={"doctype": "Leave Type", "fields": json.dumps(["name"]),
                        "order_by": "name asc", "limit_page_length": 200},
                headers=headers,
            )
        except ApiClientError as exc:
            logger.error("Failed to fetch leave types: %s", exc)
            raise LeaveServiceError(f"Failed to fetch leave types: {exc}") from exc
        message = response.json().get("message") if isinstance(response.json(), dict) else None
        return [str(row["name"]) for row in message or [] if isinstance(row, dict) and row.get("name")]

    def get_leave_balance(
        self,
        employee: Optional[str] = None,
        on_date: Optional[Any] = None,
        csrf_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return the leave balance per leave type for one employee as of `on_date` (default today).

        Each row: leave_type, total_leaves, leaves_taken, leaves_pending_approval,
        expired_leaves, remaining_leaves. Leave types without an allocation (e.g.
        Leave Without Pay) are not included.
        """
        employee_filter = employee or self.auth_service.getSession()
        if not employee_filter:
            raise LeaveAuthError("No authenticated user is available for the leave balance.")
        headers = {
            "accept": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        csrf = csrf_token or self.api_client.get_cookies().get("csrf_token")
        if csrf:
            headers["x-frappe-csrf-token"] = csrf
        try:
            response = self.api_client.post(
                self.leave_details_endpoint,
                data=urllib.parse.urlencode(
                    {"employee": employee_filter, "date": str(on_date or date.today())}
                ),
                headers=headers,
            )
        except ApiClientError as exc:
            logger.error("Failed to fetch leave balance: %s", exc)
            raise LeaveServiceError(f"Failed to fetch leave balance: {exc}") from exc
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        allocation = message.get("leave_allocation") if isinstance(message, dict) else None
        rows: List[Dict[str, Any]] = []
        for leave_type, numbers in (allocation or {}).items():
            numbers = numbers if isinstance(numbers, dict) else {}
            rows.append({"leave_type": leave_type, **{k: numbers.get(k, 0) for k in self._BALANCE_KEYS}})
        return rows

    @staticmethod
    def _normalize(data: Any) -> List[Dict[str, Any]]:
        """Turn Frappe's {"message": {"keys": [...], "values": [[...]]}} into dict rows."""
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict):
            return []
        keys = message.get("keys") or []
        rows = [dict(zip(keys, values)) for values in message.get("values") or []]
        for row in rows:  # the server pads some names with double spaces
            if isinstance(row.get("employee_name"), str):
                row["employee_name"] = " ".join(row["employee_name"].split())
        return rows
