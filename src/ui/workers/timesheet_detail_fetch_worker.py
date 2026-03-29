"""
timesheet_detail_fetch_worker.py
--------------------------------
A QRunnable worker that fetches one timesheet detail record from the
TimesheetService on a background thread.
"""
import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QRunnable, QObject, Signal, Slot

from src.services.timesheet_service import TimesheetService, TimesheetServiceError

logger = logging.getLogger(__name__)


class _TimesheetDetailFetchSignals(QObject):
    """Thread-safe signal carrier for TimesheetDetailFetchWorker."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)


class TimesheetDetailFetchWorker(QRunnable):
    """Background worker that loads one normalized timesheet detail payload."""

    def __init__(
        self,
        service: TimesheetService,
        name: str,
        csrf_token: Optional[str] = None,
    ):
        super().__init__()
        self.service = service
        self.name = name
        self.csrf_token = csrf_token
        self.signals = _TimesheetDetailFetchSignals()

    @Slot()
    def run(self) -> None:
        """Executes on the QThreadPool thread. Never touch QWidgets here."""
        logger.debug("TimesheetDetailFetchWorker.run(): name=%s", self.name)
        try:
            detail: Dict[str, Any] = self.service.get_timesheet_detail(
                name=self.name,
                csrf_token=self.csrf_token,
            )
            self.signals.result_ready.emit(detail)
        except TimesheetServiceError as exc:
            logger.error("TimesheetDetailFetchWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in TimesheetDetailFetchWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
