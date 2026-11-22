"""Single place that wires the API client and services.

Both front ends (GUI and CLI) start from `build_app()` so they always share the
same wiring: one ApiClient, session recovery through AuthService, and the same
keyring-backed credentials.
"""

from dataclasses import dataclass
from typing import Optional

from src.api import ApiClient
from src.core import prefs
from src.persistence.credential_storage import CredentialStorage
from src.persistence.session_store import SessionStore
from src.services.activity_service import ActivityService
from src.services.auth_service import AuthService
from src.services.employee_service import EmployeeService
from src.services.leave_service import LeaveService
from src.services.project_service import ProjectService
from src.services.timesheet_service import TimesheetService

DEFAULT_BASE_URL = prefs.DEFAULT_BASE_URL


@dataclass
class AppContext:
    api_client: ApiClient
    auth: AuthService
    projects: ProjectService
    activities: ActivityService
    timesheets: TimesheetService
    leave: LeaveService
    employees: EmployeeService


def build_app(base_url: Optional[str] = None) -> AppContext:
    """Construct the service graph. Makes no network calls.

    The server URL comes from `base_url`, else the saved `url` preference.
    """
    api_client = ApiClient(base_url=base_url or prefs.get_url())
    # AuthService must be created before the other services: it installs
    # api_client.auth_provider so every request can recover its session.
    auth = AuthService(api_client, CredentialStorage(), session_store=SessionStore())
    return AppContext(
        api_client=api_client,
        auth=auth,
        projects=ProjectService(api_client),
        activities=ActivityService(api_client),
        timesheets=TimesheetService(api_client, auth),
        leave=LeaveService(api_client, auth),
        employees=EmployeeService(api_client, auth),
    )
