"""
timesheet_detail_presenter.py
-----------------------------
Coordinator between the TimesheetDetailView and the TimesheetService:
shows one timesheet and applies the edit / delete / submit actions.
"""
import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot, QThreadPool

from src.services.timesheet_service import TimesheetService
from src.ui.views.edit_entry_dialog import EditEntryDialog
from src.ui.views.timesheet_detail_view import TimesheetDetailView
from src.ui.workers.call_worker import CallWorker
from src.ui.workers.timesheet_detail_fetch_worker import TimesheetDetailFetchWorker

logger = logging.getLogger(__name__)


class _Job(QObject):
    """Receives one worker's result on the GUI thread.

    Closures connected straight to a worker's signals would run on the worker
    thread (unsafe for widgets); a QObject living here is called through a queued
    connection instead.
    """

    def __init__(self, on_done: Callable[[Any], None], on_error: Callable[[str], None], parent: QObject):
        super().__init__(parent)
        self._on_done, self._on_error = on_done, on_error

    @Slot(object)
    def done(self, result: Any) -> None:
        try:
            self._on_done(result)
        finally:
            self.deleteLater()

    @Slot(str)
    def failed(self, message: str) -> None:
        try:
            self._on_error(message)
        finally:
            self.deleteLater()


class TimesheetDetailPresenter(QObject):
    """Manages the Timesheet Detail screen lifecycle."""

    data_changed = Signal()          # something was saved, deleted or submitted
    timesheet_deleted = Signal()     # the open timesheet no longer exists

    def __init__(
        self,
        view: TimesheetDetailView,
        service: TimesheetService,
        project_service: Any = None,
        activity_service: Any = None,
    ):
        super().__init__()
        self.view = view
        self.service = service
        self.project_service = project_service
        self.activity_service = activity_service
        self._current_name: str = ""

        view.edit_entry_requested.connect(self.edit_entry)
        view.delete_entry_requested.connect(self.delete_entry)
        view.submit_requested.connect(self.submit_timesheet)
        view.delete_timesheet_requested.connect(self.delete_timesheet)

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

    # -- actions -----------------------------------------------------------
    def _run(self, fn: Callable[[], Any], on_done: Callable[[Any], None], failure_title: str) -> None:
        """Run `fn` off the GUI thread; then `on_done(result)` or an error dialog."""
        worker = CallWorker(fn)
        job = _Job(on_done, lambda message: self._failed(failure_title, message), parent=self)
        worker.signals.result_ready.connect(job.done, Qt.QueuedConnection)
        worker.signals.error_occurred.connect(job.failed, Qt.QueuedConnection)
        self.view.set_loading(True)
        QThreadPool.globalInstance().start(worker)

    def _failed(self, title: str, message: str) -> None:
        self.view.set_loading(False)
        self.view.show_error_titled(title, message)
        logger.error("TimesheetDetailPresenter: %s — %s", title, message)

    def _after_change(self, _result: Any = None) -> None:
        self.data_changed.emit()
        self._fetch(self._current_name)

    @Slot(str)
    def edit_entry(self, row_name: str) -> None:
        entry = self.view.entry(row_name)
        if not entry:
            return
        if self.project_service is None or self.activity_service is None:
            self.view.show_error_titled("Edit entry", "Editing is not available in this session.")
            return
        self._run(
            lambda: {
                "projects": self.project_service.get_projects(page_length=200),
                "activities": self.activity_service.get_activity_names(),
            },
            lambda options: self._show_edit_dialog(row_name, entry, options),
            "Could not load projects and activities",
        )

    def _show_edit_dialog(self, row_name: str, entry: dict, options: dict) -> None:
        self.view.set_loading(False)
        dialog = EditEntryDialog(entry, options.get("projects") or [], options.get("activities") or [], parent=self.view)
        if dialog.exec():
            self.apply_entry_changes(row_name, dialog.get_changes())
        else:
            self._fetch(self._current_name)

    def apply_entry_changes(self, row_name: str, changes: dict) -> None:
        if not changes:
            self._fetch(self._current_name)
            return
        name = self._current_name
        self._run(
            lambda: self.service.update_time_log(name, row_name, **changes),
            self._after_change,
            "Could not save the entry",
        )

    @Slot(str)
    def delete_entry(self, row_name: str) -> None:
        entry = self.view.entry(row_name)
        if not entry:
            return
        what = f"{entry.get('project_name') or entry.get('project')} · {entry.get('activity_type')} · {entry.get('description')}"
        if not self.view.confirm("Delete entry", f"Delete this entry?\n\n{what}"):
            return
        name = self._current_name
        self._run(lambda: self.service.delete_time_log(name, row_name), self._after_change, "Could not delete the entry")

    @Slot()
    def submit_timesheet(self) -> None:
        name = self._current_name
        if not self.view.confirm(
            "Submit timesheet",
            f"Submit {name} for approval?\n\nYou cannot undo this yourself.",
        ):
            return
        self._run(lambda: self.service.submit_timesheet(name), self._after_change, "Could not submit the timesheet")

    @Slot()
    def delete_timesheet(self) -> None:
        name = self._current_name
        if not self.view.confirm("Delete timesheet", f"Delete {name} and all of its entries?"):
            return

        def done(_result: Any) -> None:
            self.view.set_loading(False)
            self.data_changed.emit()
            self.timesheet_deleted.emit()

        self._run(lambda: self.service.delete_timesheet(name), done, "Could not delete the timesheet")
