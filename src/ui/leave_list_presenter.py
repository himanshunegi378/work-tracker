"""Coordinates LeaveListView and LeaveService; the network call runs on a worker thread."""

import logging
from typing import Optional

from PySide6.QtCore import QObject

from src.services.leave_service import LeaveService
from src.ui.views.leave_list_view import LeaveListView
from src.ui.workers.call_worker import run_in_background

logger = logging.getLogger(__name__)


class LeaveListPresenter(QObject):
    def __init__(self, view: LeaveListView, service: LeaveService, employee_service=None, page_size: int = 20):
        super().__init__()
        self.view = view
        self.service = service
        self.employee_service = employee_service
        self.page_size = page_size
        self._status = ""
        self._leave_type = ""
        self._types_loaded = False
        self._employees_loaded = False
        self._employee = ""
        self._balance_employee: Optional[str] = None
        self._page = 0
        self._request_id = 0  # drop results of superseded requests
        self.view.fetch_requested.connect(self._on_fetch_requested)

    def refresh(self) -> None:
        """Reload the first page; called whenever the user opens the Leave screen."""
        if not self._types_loaded:
            self._load_types()
        if not self._employees_loaded:
            self._load_employees()
        self._fetch(
            self.view.selected_status(), self.view.selected_type(), self.view.selected_employee(), 0,
            force_balance=True,
        )

    def _load_types(self) -> None:
        """Fetch the server's leave types once; a failure leaves just 'All types'."""
        run_in_background(
            self.service.get_leave_types, self._on_types,
            lambda msg: logger.warning("Leave types unavailable: %s", msg), self,
        )

    def _load_employees(self) -> None:
        """Fetch the people you may see once; a failure leaves just Me / Everyone."""
        if self.employee_service is None:
            return
        run_in_background(
            lambda: self.employee_service.get_employees(include_self=False), self._on_employees,
            lambda msg: logger.warning("Employees unavailable: %s", msg), self,
        )

    def _on_employees(self, people: list) -> None:
        self._employees_loaded = True
        self.view.set_employees(people)

    def _load_balances(self, employee: str) -> None:
        """Fetch one person's balances. "Everyone" has no single balance, so the strip is cleared."""
        self._balance_employee = employee
        if employee == "*":
            self.view.display_balances([])
            return
        run_in_background(
            lambda: self.service.get_leave_balance(employee=employee or None),
            lambda rows: self._on_balances(employee, rows),
            lambda msg: logger.warning("Leave balance unavailable: %s", msg), self,
        )

    def _on_balances(self, employee: str, rows: list) -> None:
        if employee == self._balance_employee:  # ignore a slow reply for a person no longer selected
            self.view.display_balances(rows)

    def _on_types(self, types: list) -> None:
        self._types_loaded = True
        self.view.set_leave_types(types)

    def _on_fetch_requested(self, status: str, leave_type: str, employee: str, page: int) -> None:
        self._fetch(status, leave_type, employee, page)

    def _fetch(self, status: str, leave_type: str, employee: str, page: int, force_balance: bool = False) -> None:
        self._status, self._leave_type, self._employee, self._page = status, leave_type, employee, page
        if force_balance or employee != self._balance_employee:
            self._load_balances(employee)
        self._request_id += 1
        request_id = self._request_id
        start, size = page * self.page_size, self.page_size

        self.view.set_loading(True)
        run_in_background(
            lambda: self.service.get_leave_applications(
                start=start, page_length=size, status=status or None,
                leave_type=leave_type or None, employee=None if employee in ("", "*") else employee,
                all_employees=employee == "*"),
            lambda rows: self._on_result(request_id, page, rows),
            lambda msg: self._on_error(request_id, msg), self,
        )

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
