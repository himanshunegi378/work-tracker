from src.api import AuthenticationRequiredError


class TimesheetServiceError(Exception):
    """Raised when a timesheet operation fails."""


class TimesheetAuthError(TimesheetServiceError, AuthenticationRequiredError):
    """No logged-in user. Still a TimesheetServiceError (GUI handlers keep working),
    and also an AuthenticationRequiredError so the CLI can exit with the login hint."""

    def __init__(self, message: str):
        AuthenticationRequiredError.__init__(self, message)
