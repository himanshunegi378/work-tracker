"""Exit codes and error handling shared by every command."""

import sys
from typing import Callable

OK = 0
ERROR = 1
USAGE = 2
NOT_LOGGED_IN = 3
GUI_UNAVAILABLE = 4


class CliError(Exception):
    """An expected failure with a user-facing message and an exit code."""

    def __init__(self, message: str, exit_code: int = ERROR, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.hint = hint


def _is_auth_error(exc: BaseException) -> bool:
    """True if `exc`, or anything it wraps (services re-raise API errors), is a login problem."""
    from src.api import AuthenticationRequiredError

    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, AuthenticationRequiredError):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


def exit_code_for(exc: BaseException) -> int:
    """Map an exception to a process exit code."""
    if isinstance(exc, CliError):
        return exc.exit_code
    if _is_auth_error(exc):
        return NOT_LOGGED_IN
    return ERROR


def message_for(exc: BaseException) -> str:
    if not isinstance(exc, CliError) and _is_auth_error(exc):
        return "Not logged in. Run `samta-tracker login`."
    return getattr(exc, "message", None) or str(exc) or exc.__class__.__name__


def run_guarded(fn: Callable[[], None], report: Callable[[str], None]) -> int:
    """Run `fn`, converting exceptions into a message and an exit code."""
    try:
        fn()
        return OK
    except KeyboardInterrupt:
        report("Cancelled.")
        return ERROR
    except Exception as exc:  # noqa: BLE001 - top-level boundary
        report(message_for(exc))
        hint = getattr(exc, "hint", "")
        if hint:
            report(hint)
        return exit_code_for(exc)


def handle_errors(fn: Callable) -> Callable:
    """Decorator for command functions: turn failures into a message + exit code.

    Typer already handles usage errors (exit 2) and --help/--version (exit 0);
    this covers everything raised while a command actually runs.
    """
    import functools

    import typer

    from src.cli.output import error

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except KeyboardInterrupt:
            error("Cancelled.")
            raise typer.Exit(ERROR)
        except Exception as exc:  # noqa: BLE001 - command boundary
            error(message_for(exc))
            hint = getattr(exc, "hint", "")
            if hint:
                print(hint, file=sys.stderr)
            raise typer.Exit(exit_code_for(exc))

    return wrapper
