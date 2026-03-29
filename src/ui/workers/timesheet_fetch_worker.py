"""
timesheet_fetch_worker.py
-------------------------
A QRunnable worker that fetches timesheets from the TimesheetService on a
background thread, then signals results (or errors) back to the main thread.
"""
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QRunnable, QObject, Signal, Slot

from src.services.timesheet_service import TimesheetService, TimesheetServiceError

logger = logging.getLogger(__name__)


class _TimesheetFetchSignals(QObject):
    """Thread-safe signal carrier for TimesheetFetchWorker."""

    result_ready = Signal(list)
    error_occurred = Signal(str)


class TimesheetFetchWorker(QRunnable):
    """Background worker that loads paginated timesheet rows."""

    def __init__(
        self,
        service: TimesheetService,
        start: int = 0,
        page_length: int = 20,
        employee: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ):
        super().__init__()
        self.service = service
        self.start = start
        self.page_length = page_length
        self.employee = employee
        self.csrf_token = csrf_token
        self.signals = _TimesheetFetchSignals()

    @Slot()
    def run(self) -> None:
        """Executes on the QThreadPool thread. Never touch QWidgets here."""
        logger.debug(
            "TimesheetFetchWorker.run(): start=%d page_length=%d",
            self.start,
            self.page_length,
        )
        try:
            timesheets: List[Dict[str, Any]] = self.service.get_timesheets(
                start=self.start,
                page_length=self.page_length,
                employee=self.employee,
                csrf_token=self.csrf_token,
            )
            self.signals.result_ready.emit(timesheets)
        except TimesheetServiceError as exc:
            logger.error("TimesheetFetchWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in TimesheetFetchWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
