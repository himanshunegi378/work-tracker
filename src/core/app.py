"""Single place that wires the API client and services.

Both front ends (GUI and CLI) start from `build_app()` so they always share the
same wiring: one ApiClient, session recovery through AuthService, and the same
keyring-backed credentials.
"""

from dataclasses import dataclass
from typing import Optional

from src.api import ApiClient
from src.persistence.credential_storage import CredentialStorage
from src.services.activity_service import ActivityService
from src.services.auth_service import AuthService
from src.services.project_service import ProjectService
from src.services.timesheet_service import TimesheetService

DEFAULT_BASE_URL = "https://matrix.samta.ai"


@dataclass
class AppContext:
    api_client: ApiClient
    auth: AuthService
    projects: ProjectService
    activities: ActivityService
    timesheets: TimesheetService


def build_app(base_url: Optional[str] = None) -> AppContext:
    """Construct the service graph. Makes no network calls."""
    api_client = ApiClient(base_url=base_url or DEFAULT_BASE_URL)
    # AuthService must be created before the other services: it installs
    # api_client.auth_provider so every request can recover its session.
    auth = AuthService(api_client, CredentialStorage())
    return AppContext(
        api_client=api_client,
        auth=auth,
        projects=ProjectService(api_client),
        activities=ActivityService(api_client),
        timesheets=TimesheetService(api_client, auth),
    )
