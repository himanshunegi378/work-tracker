"""
activity_selection_fetch_worker.py
----------------------------------
Background worker that loads activity names for local selection UIs.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.services.activity_service import ActivityService, ActivityServiceError

logger = logging.getLogger(__name__)


class _ActivitySelectionFetchSignals(QObject):
    """Thread-safe signal carrier for activity selection fetches."""

    result_ready = Signal(list)
    error_occurred = Signal(str)


class ActivitySelectionFetchWorker(QRunnable):
    """Fetches selection-ready activity names off the main thread."""

    def __init__(
        self,
        service: ActivityService,
        search_text: str = "",
        page_length: int = 200,
        csrf_token: Optional[str] = None,
    ):
        super().__init__()
        self.service = service
        self.search_text = search_text
        self.page_length = page_length
        self.csrf_token = csrf_token
        self.signals = _ActivitySelectionFetchSignals()

    @Slot()
    def run(self) -> None:
        logger.debug(
            "ActivitySelectionFetchWorker.run(): search='%s' page_length=%d",
            self.search_text,
            self.page_length,
        )
        try:
            activity_names: List[str] = self.service.get_activity_names(
                search_text=self.search_text,
                page_length=self.page_length,
                csrf_token=self.csrf_token,
            )
            self.signals.result_ready.emit(activity_names)
        except ActivityServiceError as exc:
            logger.error("ActivitySelectionFetchWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in ActivitySelectionFetchWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
