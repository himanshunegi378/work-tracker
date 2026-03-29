"""
timesheet_list_presenter.py
---------------------------
Coordinator between the TimesheetListView and the TimesheetService.
"""
import logging

from PySide6.QtCore import QObject, Slot, QThreadPool

from src.services.timesheet_service import TimesheetService
from src.ui.views.timesheet_list_view import TimesheetListView
from src.ui.workers.timesheet_fetch_worker import TimesheetFetchWorker

logger = logging.getLogger(__name__)


class TimesheetListPresenter(QObject):
    """Manages the Timesheet List screen lifecycle."""

    def __init__(
        self,
        view: TimesheetListView,
        service: TimesheetService,
        page_size: int = 20,
    ):
        super().__init__()
        self.view = view
        self.service = service
        self.page_size = page_size
        self._current_page: int = 0

        self.view.fetch_requested.connect(self._on_fetch_requested)

    def refresh(self) -> None:
        """Reset to page 0 and trigger a fresh fetch."""
        self._current_page = 0
        self._fetch(self._current_page)

    @Slot(int)
    def _on_fetch_requested(self, page: int) -> None:
        self._current_page = page
        self._fetch(page)

    def _fetch(self, page: int) -> None:
        """Creates and submits a worker to QThreadPool, wires its signals."""
        logger.debug("TimesheetListPresenter._fetch(): page=%d", page)
        start = page * self.page_size

        worker = TimesheetFetchWorker(
            service=self.service,
            start=start,
            page_length=self.page_size,
        )
        worker.signals.result_ready.connect(self._on_result_ready)
        worker.signals.error_occurred.connect(self._on_error_occurred)

        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    @Slot(list)
    def _on_result_ready(self, timesheets: list) -> None:
        """Receives the fetched list from the worker and updates the view."""
        self.view.display_timesheets(timesheets)
        self.view.set_page_info(
            current_page=self._current_page,
            page_size=self.page_size,
            result_count=len(timesheets),
        )
        self.view.set_loading(False)
        logger.debug(
            "TimesheetListPresenter: displayed %d timesheets on page %d",
            len(timesheets),
            self._current_page,
        )

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        """Receives error message from worker and surfaces it in the view."""
        self.view.set_loading(False)
        self.view.show_error(message)
        logger.error("TimesheetListPresenter: fetch error — %s", message)
