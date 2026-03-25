"""
smart_log_options_fetch_worker.py
---------------------------------
Background worker that fetches project and activity names for SmartLogDialog.
"""
import logging
from typing import List

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from services.project_service import ProjectService
from services.activity_service import ActivityService

logger = logging.getLogger(__name__)


class _SmartLogOptionsFetchSignals(QObject):
    """Thread-safe signal carrier for smart-log option fetches."""

    result_ready = Signal(list, list, str)


class SmartLogOptionsFetchWorker(QRunnable):
    """Fetches selection-ready project and activity names off the main thread."""

    def __init__(
        self,
        project_service: ProjectService,
        activity_service: ActivityService,
        page_length: int = 200,
    ):
        super().__init__()
        self.project_service = project_service
        self.activity_service = activity_service
        self.page_length = page_length
        self.signals = _SmartLogOptionsFetchSignals()

    @Slot()
    def run(self) -> None:
        logger.debug(
            "SmartLogOptionsFetchWorker.run(): page_length=%d",
            self.page_length,
        )

        project_names: List[str] = []
        activity_names: List[str] = []
        status_parts: List[str] = []

        try:
            project_names = self.project_service.get_project_names(
                page_length=self.page_length,
            )
        except Exception as exc:
            logger.exception("Failed to fetch project names for smart log dialog")
            status_parts.append(f"Project options are unavailable right now: {exc}")

        try:
            activity_names = self.activity_service.get_activity_names(
                page_length=self.page_length,
            )
        except Exception as exc:
            logger.exception("Failed to fetch activity names for smart log dialog")
            status_parts.append(f"Activity options are unavailable right now: {exc}")

        self.signals.result_ready.emit(
            project_names,
            activity_names,
            "\n".join(status_parts),
        )
