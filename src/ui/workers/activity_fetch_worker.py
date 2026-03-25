"""
activity_fetch_worker.py
------------------------
A QRunnable worker that fetches activities from the ActivityService on a
background thread, then signals results (or errors) back to the main thread.

Design Notes:
- Follows the PySide6 pattern: a helper QObject (_Signals) owns the signals,
  while ActivityFetchWorker(QRunnable) owns the run() logic.  This avoids the
  limitation that QRunnable itself cannot inherit QObject on Python bindings.
- All cross-thread emissions use Qt.QueuedConnection semantics automatically
  because the receiving slots live in the main thread's event loop.
"""
import logging
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QRunnable, QObject, Signal, Slot

from services.activity_service import ActivityService, ActivityServiceError

logger = logging.getLogger(__name__)


class _ActivityFetchSignals(QObject):
    """Thread-safe signal carrier for ActivityFetchWorker."""

    # Emitted when activities are fetched successfully.
    result_ready = Signal(list)          # List[Dict[str, Any]]

    # Emitted when any error occurs during the fetch.
    error_occurred = Signal(str)         # human-readable message


class ActivityFetchWorker(QRunnable):
    """
    Background worker that calls ActivityService.get_activities() and
    emits the result back to the main thread via signals.

    Usage:
        worker = ActivityFetchWorker(service, search_text, start, page_length)
        worker.signals.result_ready.connect(your_slot)
        worker.signals.error_occurred.connect(your_error_slot)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        service: ActivityService,
        search_text: str = "",
        start: int = 0,
        page_length: int = 20,
        csrf_token: Optional[str] = None,
    ):
        super().__init__()
        self.service = service
        self.search_text = search_text
        self.start = start
        self.page_length = page_length
        self.csrf_token = csrf_token

        # Public so the presenter can connect slots before submission
        self.signals = _ActivityFetchSignals()

    @Slot()
    def run(self) -> None:
        """Executes on the QThreadPool thread. Never touch QWidgets here."""
        logger.debug(
            "ActivityFetchWorker.run(): search='%s' start=%d page_length=%d",
            self.search_text,
            self.start,
            self.page_length,
        )
        try:
            activities: List[Dict[str, Any]] = self.service.get_activities(
                search_text=self.search_text,
                start=self.start,
                page_length=self.page_length,
                csrf_token=self.csrf_token,
            )
            self.signals.result_ready.emit(activities)
        except ActivityServiceError as exc:
            logger.error("ActivityFetchWorker failed: %s", exc)
            self.signals.error_occurred.emit(str(exc))
        except Exception as exc:
            # Catch-all so pool threads never crash silently
            logger.exception("Unexpected error in ActivityFetchWorker")
            self.signals.error_occurred.emit(f"Unexpected error: {exc}")
