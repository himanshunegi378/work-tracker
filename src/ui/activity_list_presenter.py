"""
activity_list_presenter.py
--------------------------
Coordinator between the ActivityListView and the ActivityService.

Responsibilities:
  - Hold current search text and page state
  - Create and submit ActivityFetchWorker instances to QThreadPool
  - Translate worker signals into view commands (display / error / loading)
  - Expose a public refresh() method so MainWindow can reset state on navigation

Design Principles Applied:
  - Single Responsibility: Presenter never touches widgets or HTTP directly
  - Dependency Injection: receives view + service instances (testable)
  - Non-Blocking: all network work delegated to QThreadPool workers
"""
import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Slot, QThreadPool

from ui.views.activity_list_view import ActivityListView
from services.activity_service import ActivityService
from ui.workers.activity_fetch_worker import ActivityFetchWorker
from ui.workers.activity_selection_fetch_worker import ActivitySelectionFetchWorker

logger = logging.getLogger(__name__)


class ActivityListPresenter(QObject):
    """
    Manages the Activity List screen lifecycle.

    Args:
        view:    The ActivityListView instance to drive.
        service: The ActivityService used to fetch data from the backend.
        page_size: Records to request per page (default 20).
    """

    def __init__(
        self,
        view: ActivityListView,
        service: ActivityService,
        page_size: int = 20,
    ):
        super().__init__()
        self.view = view
        self.service = service
        self.page_size = page_size

        # State
        self._current_page: int = 0
        self._current_search: str = ""
        self._cached_activity_names: List[str] = []
        self._selection_cache_error: Optional[str] = None
        self._selection_cache_loading: bool = False

        # Connect view signals → presenter slots
        self.view.fetch_requested.connect(self._on_fetch_requested)

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Resets to page 0 with the current search text and triggers a fetch.
        Called by MainWindow whenever the user navigates to the Activities screen.
        """
        self._current_page = 0
        self._fetch(self._current_search, self._current_page)

    def refresh_selection_cache(self) -> None:
        """Warm a reusable activity-name cache for selection UIs."""
        if self._selection_cache_loading:
            return

        worker = ActivitySelectionFetchWorker(
            service=self.service,
            page_length=max(self.page_size * 5, 100),
        )
        worker.signals.result_ready.connect(self._on_selection_result_ready)
        worker.signals.error_occurred.connect(self._on_selection_error_occurred)

        self._selection_cache_loading = True
        self._selection_cache_error = None
        QThreadPool.globalInstance().start(worker)

    def get_cached_activity_names(self) -> List[str]:
        """Return the most recently fetched activity-name cache."""
        return list(self._cached_activity_names)

    def get_selection_cache_error(self) -> Optional[str]:
        """Return the last selection-cache error, if any."""
        return self._selection_cache_error

    def is_selection_cache_loading(self) -> bool:
        """Expose whether the selection cache is being refreshed."""
        return self._selection_cache_loading

    # ── Private slots ──────────────────────────────────────────────────────────

    @Slot(str, int)
    def _on_fetch_requested(self, search_text: str, page: int) -> None:
        """Slot responding to the user changing search text or clicking pagination."""
        self._current_search = search_text
        self._current_page = page
        self._fetch(search_text, page)

    def _fetch(self, search_text: str, page: int) -> None:
        """Creates and submits a worker to QThreadPool, wires its signals."""
        logger.debug("ActivityListPresenter._fetch(): text='%s' page=%d", search_text, page)
        start = page * self.page_size

        worker = ActivityFetchWorker(
            service=self.service,
            search_text=search_text,
            start=start,
            page_length=self.page_size,
        )

        # Connect worker signals — must use Qt.QueuedConnection to safely
        # hand results back to the main (GUI) thread from the pool thread.
        worker.signals.result_ready.connect(self._on_result_ready)
        worker.signals.error_occurred.connect(self._on_error_occurred)

        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    # ── Worker signal handlers (main thread) ───────────────────────────────────

    @Slot(list)
    def _on_result_ready(self, activities: list) -> None:
        """Receives the fetched list from the worker and updates the view."""
        self.view.display_activities(activities)
        self.view.set_page_info(
            current_page=self._current_page,
            page_size=self.page_size,
            result_count=len(activities),
        )
        self.view.set_loading(False)
        logger.debug(
            "ActivityListPresenter: displayed %d activities on page %d",
            len(activities),
            self._current_page,
        )

    @Slot(list)
    def _on_selection_result_ready(self, activity_names: list) -> None:
        """Stores a reusable activity-name list for smart-log selection."""
        self._cached_activity_names = [
            str(name).strip() for name in activity_names if str(name).strip()
        ]
        self._selection_cache_loading = False
        self._selection_cache_error = None
        logger.debug(
            "ActivityListPresenter: cached %d activity names for selection",
            len(self._cached_activity_names),
        )

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        """Receives error message from worker and surfaces it in the view."""
        self.view.set_loading(False)
        self.view.show_error(message)
        logger.error("ActivityListPresenter: fetch error — %s", message)

    @Slot(str)
    def _on_selection_error_occurred(self, message: str) -> None:
        """Captures selection-cache failures without breaking the activity screen."""
        self._selection_cache_loading = False
        self._selection_cache_error = message
        logger.error("ActivityListPresenter: selection cache error — %s", message)
