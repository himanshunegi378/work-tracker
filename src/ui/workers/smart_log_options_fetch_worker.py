"""
smart_log_options_fetch_worker.py
---------------------------------
Background worker that fetches smart-log context for SmartLogDialog.
"""
import logging
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from services.project_service import ProjectService
from services.activity_service import ActivityService
from services.timesheet_service import TimesheetService

logger = logging.getLogger(__name__)


class _SmartLogOptionsFetchSignals(QObject):
    """Thread-safe signal carrier for smart-log option fetches."""

    result_ready = Signal(list, list, dict, str)


class SmartLogOptionsFetchWorker(QRunnable):
    """Fetches selection-ready projects, activities, and smart-log defaults off-thread."""

    def __init__(
        self,
        project_service: ProjectService,
        activity_service: ActivityService,
        timesheet_service: TimesheetService,
        page_length: int = 200,
    ):
        super().__init__()
        self.project_service = project_service
        self.activity_service = activity_service
        self.timesheet_service = timesheet_service
        self.page_length = page_length
        self.signals = _SmartLogOptionsFetchSignals()

    @Slot()
    def run(self) -> None:
        logger.debug(
            "SmartLogOptionsFetchWorker.run(): page_length=%d",
            self.page_length,
        )

        project_options: List[Dict[str, str]] = []
        activity_names: List[str] = []
        smart_defaults: Optional[Dict[str, object]] = None
        status_parts: List[str] = []

        try:
            projects = self.project_service.get_projects(
                start=0,
                page_length=self.page_length,
            )
            project_options = [
                {"id": str(project.get("id") or ""), "name": str(project.get("name") or "")}
                for project in projects
                if project.get("id") and project.get("name")
            ]
        except Exception as exc:
            logger.exception("Failed to fetch project options for smart log dialog")
            status_parts.append(f"Project options are unavailable right now: {exc}")

        try:
            activity_names = self.activity_service.get_activity_names(
                page_length=self.page_length,
            )
        except Exception as exc:
            logger.exception("Failed to fetch activity names for smart log dialog")
            status_parts.append(f"Activity options are unavailable right now: {exc}")

        try:
            smart_defaults = self.timesheet_service.get_latest_smart_log_state()
        except Exception as exc:
            logger.exception("Failed to fetch latest smart log state")
            status_parts.append(f"Latest timesheet context is unavailable right now: {exc}")

        self.signals.result_ready.emit(
            project_options,
            activity_names,
            smart_defaults or {},
            "\n".join(status_parts),
        )
