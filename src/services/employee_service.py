import json
import logging
from typing import Dict, List, Optional

from src.api import ApiClient, ApiClientError
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class EmployeeServiceError(Exception):
    """Raised when the employee list cannot be loaded."""


class EmployeeService:
    """Lists the employees this account is allowed to see (shared by leave and timesheets)."""

    def __init__(self, api_client: ApiClient, auth_service: AuthService):
        self.api_client = api_client
        self.auth_service = auth_service

    def get_employees(self, include_self: bool = True, csrf_token: Optional[str] = None) -> List[Dict[str, str]]:
        """Return [{"employee": id, "employee_name": name}] sorted by name; the server enforces permissions."""
        headers = {"accept": "application/json", "x-requested-with": "XMLHttpRequest"}
        csrf = csrf_token or self.api_client.get_cookies().get("csrf_token")
        if csrf:
            headers["x-frappe-csrf-token"] = csrf
        try:
            response = self.api_client.get(
                "/api/method/frappe.client.get_list",
                params={"doctype": "Employee", "fields": json.dumps(["name", "employee_name"]),
                        "order_by": "employee_name asc", "limit_page_length": 1000},
                headers=headers,
            )
        except ApiClientError as exc:
            logger.error("Failed to fetch employees: %s", exc)
            raise EmployeeServiceError(f"Failed to fetch employees: {exc}") from exc
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        me = None if include_self else self.auth_service.getSession()
        people = [
            {"employee": str(row["name"]),
             "employee_name": " ".join(str(row.get("employee_name") or row["name"]).split())}
            for row in message or [] if isinstance(row, dict) and row.get("name") and row["name"] != me
        ]
        return sorted(people, key=lambda p: p["employee_name"].lower())
