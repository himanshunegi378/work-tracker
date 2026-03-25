"""
smart_log_save_worker.py
------------------------
Background worker that saves a smart-log submission into today's timesheet.
"""
import logging
from typing import Dict

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from services.timesheet_service import TimesheetService, TimesheetServiceError

logger = logging.getLogger(__name__)


class _SmartLogSaveSignals(QObject):
    """Thread-safe signal carrier for smart-log save requests."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)


class SmartLogSaveWorker(QRunnable):
    """Persist a smart log into the current user's timesheet off the GUI thread."""

    def __init__(
        self,
        service: TimesheetService,
        payload: Dict[str, object],
        interval_seconds: int,
    ):
        super().__init__()
        self.service = service
        self.payload = payload
        self.interval_seconds = interval_seconds
        self.signals = _SmartLogSaveSignals()

    @Slot()
    def run(self) -> None:
        logger.debug("SmartLogSaveWorker.run(): saving smart-log payload to timesheet")
        try:
            detail = self.service.save_timesheet_log(
                project_id=str(self.payload["project_id"]),
                project_name=str(self.payload["project_name"]),
                activity=str(self.payload["activity_name"]),
                description=str(self.payload["description"]),
                is_billable=bool(self.payload["is_billable"]),
                interval_seconds=self.interval_seconds,
            )
            self.signals.result_ready.emit(detail)
        except TimesheetServiceError as exc:
            logger.error("SmartLogSaveWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in SmartLogSaveWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
