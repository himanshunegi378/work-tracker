"""
home_presenter.py  (migrated)
------------------------------
Coordinator between HomeView and ProjectService.

Responsibilities:
  - Hold current search text and page state
  - Spawn ProjectFetchWorker on QThreadPool for non-blocking fetches
  - Translate worker signals into view commands
  - Cache fetched project names for downstream consumers (SmartLogDialog)
  - Expose refresh() called by MainWindow on navigation

Design Principles:
  - Dependency Injection: receives view + service (fully testable)
  - Single Responsibility: no widget API calls, no HTTP calls
  - Non-Blocking: all network ops run in QThreadPool
"""
import logging
from typing import List

from PySide6.QtCore import QObject, QThreadPool, Slot

from src.services.project_service import ProjectService
from src.ui.views.home_view import HomeView
from src.ui.workers.project_fetch_worker import ProjectFetchWorker

logger = logging.getLogger(__name__)


class HomePresenter(QObject):
    """
    Manages the Projects list screen lifecycle.

    Args:
        view:      The HomeView instance to drive.
        service:   ProjectService used to fetch data from Frappe.
        page_size: Records per page (default 20).
    """

    def __init__(
        self,
        view: HomeView,
        service: ProjectService,
        page_size: int = 20,
    ):
        super().__init__()
        self.view      = view
        self.service   = service
        self.page_size = page_size

        # State
        self._current_page:   int       = 0
        self._current_search: str       = ""
        self._cached_projects: List[dict] = []  # latest result set

        # Wire view signal → presenter slot
        self.view.fetch_requested.connect(self._on_fetch_requested)

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Resets to page 0 and triggers a fresh fetch.
        Called by MainWindow whenever the user navigates to the Projects screen.
        """
        self._current_page = 0
        self._fetch(self._current_search, self._current_page)

    def refresh_projects(self) -> None:
        """Alias kept for backward-compat call-sites in MainWindow."""
        self.refresh()

    def get_cached_project_names(self) -> List[str]:
        """
        Returns project names from the most recent successful fetch.
        Used by SmartLogDialog to populate its combo box without a second API call.
        """
        return [p.get("name", "") for p in self._cached_projects if p.get("name")]

    # ── Private slots ──────────────────────────────────────────────────────────

    @Slot(str, int)
    def _on_fetch_requested(self, search_text: str, page: int) -> None:
        self._current_search = search_text
        self._current_page   = page
        self._fetch(search_text, page)

    def _fetch(self, search_text: str, page: int) -> None:
        """Submits a ProjectFetchWorker to the global QThreadPool."""
        logger.debug(
            "HomePresenter._fetch(): text='%s' page=%d", search_text, page
        )
        start  = page * self.page_size
        worker = ProjectFetchWorker(
            service=self.service,
            search_text=search_text,
            start=start,
            page_length=self.page_size,
        )
        worker.signals.result_ready.connect(self._on_result_ready)
        worker.signals.error_occurred.connect(self._on_error_occurred)

        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    # ── Worker signal handlers ─────────────────────────────────────────────────

    @Slot(list)
    def _on_result_ready(self, projects: list) -> None:
        self._cached_projects = projects
        self.view.display_projects(projects)
        self.view.set_page_info(
            current_page=self._current_page,
            page_size=self.page_size,
            result_count=len(projects),
        )
        self.view.set_loading(False)
        logger.debug(
            "HomePresenter: displayed %d projects on page %d",
            len(projects), self._current_page,
        )

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        self.view.set_loading(False)
        self.view.show_error(message)
        logger.error("HomePresenter: fetch error — %s", message)
