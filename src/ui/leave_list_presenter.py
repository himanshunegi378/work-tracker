"""Coordinates LeaveListView and LeaveService; the network call runs on a worker thread."""

import logging
from typing import Optional

from PySide6.QtCore import QObject, QThreadPool

from src.services.leave_service import LeaveService
from src.ui.views.leave_list_view import LeaveListView
from src.ui.workers.call_worker import CallWorker

logger = logging.getLogger(__name__)


class LeaveListPresenter(QObject):
    def __init__(self, view: LeaveListView, service: LeaveService, page_size: int = 20):
        super().__init__()
        self.view = view
        self.service = service
        self.page_size = page_size
        self._status = ""
        self._leave_type = ""
        self._types_loaded = False
        self._page = 0
        self._request_id = 0  # drop results of superseded requests
        self.view.fetch_requested.connect(self._on_fetch_requested)

    def refresh(self) -> None:
        """Reload the first page; called whenever the user opens the Leave screen."""
        if not self._types_loaded:
            self._load_types()
        self._load_balances()
        self._fetch(self.view.selected_status(), self.view.selected_type(), 0)

    def _load_types(self) -> None:
        """Fetch the server's leave types once; a failure leaves just 'All types'."""
        worker = CallWorker(self.service.get_leave_types)
        worker.signals.result_ready.connect(self._on_types)
        worker.signals.error_occurred.connect(lambda msg: logger.warning("Leave types unavailable: %s", msg))
        QThreadPool.globalInstance().start(worker)

    def _load_balances(self) -> None:
        """Fetch leave balances on every open; a failure just leaves the strip as it was."""
        worker = CallWorker(self.service.get_leave_balance)
        worker.signals.result_ready.connect(self.view.display_balances)
        worker.signals.error_occurred.connect(lambda msg: logger.warning("Leave balance unavailable: %s", msg))
        QThreadPool.globalInstance().start(worker)

    def _on_types(self, types: list) -> None:
        self._types_loaded = True
        self.view.set_leave_types(types)

    def _on_fetch_requested(self, status: str, leave_type: str, page: int) -> None:
        self._fetch(status, leave_type, page)

    def _fetch(self, status: str, leave_type: str, page: int) -> None:
        self._status, self._leave_type, self._page = status, leave_type, page
        self._request_id += 1
        request_id = self._request_id
        start, size = page * self.page_size, self.page_size

        worker = CallWorker(lambda: self.service.get_leave_applications(
            start=start, page_length=size, status=status or None,
            leave_type=leave_type or None))
        worker.signals.result_ready.connect(lambda rows: self._on_result(request_id, page, rows))
        worker.signals.error_occurred.connect(lambda msg: self._on_error(request_id, msg))
        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    def _on_result(self, request_id: int, page: int, rows: list) -> None:
        if request_id != self._request_id:
            return
        self.view.display_leaves(rows, first_number=page * self.page_size + 1)
        self.view.set_page_info(page, self.page_size, len(rows))
        self.view.set_loading(False)

    def _on_error(self, request_id: int, message: str) -> None:
        if request_id != self._request_id:
            return
        logger.error("LeaveListPresenter: fetch error — %s", message)
        self.view.set_loading(False)
        self.view.show_error(message)
