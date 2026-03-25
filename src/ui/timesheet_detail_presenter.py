"""
timesheet_detail_presenter.py
-----------------------------
Coordinator between the TimesheetDetailView and the TimesheetService.
"""
import logging

from PySide6.QtCore import QObject, Slot, QThreadPool

from services.timesheet_service import TimesheetService
from ui.views.timesheet_detail_view import TimesheetDetailView
from ui.workers.timesheet_detail_fetch_worker import TimesheetDetailFetchWorker

logger = logging.getLogger(__name__)


class TimesheetDetailPresenter(QObject):
    """Manages the Timesheet Detail screen lifecycle."""

    def __init__(self, view: TimesheetDetailView, service: TimesheetService):
        super().__init__()
        self.view = view
        self.service = service
        self._current_name: str = ""

    def load_timesheet(self, name: str) -> None:
        """Fetch and render one timesheet detail payload."""
        self._current_name = name
        self._fetch(name)

    def _fetch(self, name: str) -> None:
        worker = TimesheetDetailFetchWorker(service=self.service, name=name)
        worker.signals.result_ready.connect(self._on_result_ready)
        worker.signals.error_occurred.connect(self._on_error_occurred)

        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def _on_result_ready(self, detail: dict) -> None:
        self.view.display_timesheet_detail(detail)
        self.view.set_loading(False)
        logger.debug("TimesheetDetailPresenter: displayed detail for %s", self._current_name)

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        self.view.set_loading(False)
        self.view.show_error(message)
        logger.error("TimesheetDetailPresenter: fetch error — %s", message)
