"""
project_fetch_worker.py
-----------------------
A QRunnable worker that fetches projects from ProjectService on a background
thread and signals results (or errors) back to the main (GUI) thread.

Mirrors ActivityFetchWorker for consistency across the architecture.
"""
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.services.project_service import ProjectService, ProjectServiceError

logger = logging.getLogger(__name__)


class _ProjectFetchSignals(QObject):
    """Thread-safe signal carrier for ProjectFetchWorker."""
    result_ready   = Signal(list)   # List[Dict[str, Any]]
    error_occurred = Signal(str)    # human-readable error message


class ProjectFetchWorker(QRunnable):
    """
    Fetches project data off the main thread.

    Usage:
        worker = ProjectFetchWorker(service, search_text, start, page_length)
        worker.signals.result_ready.connect(your_slot)
        worker.signals.error_occurred.connect(your_error_slot)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        service: ProjectService,
        search_text: str = "",
        start: int = 0,
        page_length: int = 20,
        filters: str = "{}",
        csrf_token: Optional[str] = None,
    ):
        super().__init__()
        self.service     = service
        self.search_text = search_text
        self.start       = start
        self.page_length = page_length
        self.filters     = filters
        self.csrf_token  = csrf_token
        self.signals     = _ProjectFetchSignals()

    @Slot()
    def run(self) -> None:
        """Executes on the QThreadPool thread. Never touch QWidgets here."""
        logger.debug(
            "ProjectFetchWorker.run(): search='%s' start=%d page_length=%d",
            self.search_text, self.start, self.page_length,
        )
        try:
            projects: List[Dict[str, Any]] = self.service.get_projects(
                search_text=self.search_text,
                start=self.start,
                page_length=self.page_length,
                filters=self.filters,
                csrf_token=self.csrf_token,
            )
            self.signals.result_ready.emit(projects)
        except ProjectServiceError as exc:
            logger.error("ProjectFetchWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in ProjectFetchWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
