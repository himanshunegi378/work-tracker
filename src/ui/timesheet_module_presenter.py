"""
timesheet_module_presenter.py
-----------------------------
Coordinates the timesheet list and detail subviews inside the Timesheets module.
"""
from PySide6.QtCore import QObject, Signal, Slot

from src.services.timesheet_service import TimesheetService
from src.ui.timesheet_detail_presenter import TimesheetDetailPresenter
from src.ui.timesheet_list_presenter import TimesheetListPresenter
from src.ui.views.timesheet_module_view import TimesheetModuleView


class TimesheetModulePresenter(QObject):
    """Owns list/detail navigation for the Timesheets module."""

    data_changed = Signal()  # an entry or timesheet was changed from the detail screen

    def __init__(
        self,
        view: TimesheetModuleView,
        service: TimesheetService,
        page_size: int = 20,
        project_service=None,
        activity_service=None,
    ):
        super().__init__()
        self.view = view
        self.service = service
        self.list_presenter = TimesheetListPresenter(view.list_view, service, page_size=page_size)
        self.detail_presenter = TimesheetDetailPresenter(
            view.detail_view, service, project_service=project_service, activity_service=activity_service
        )
        self.detail_presenter.data_changed.connect(self.data_changed)
        self.detail_presenter.timesheet_deleted.connect(self._on_timesheet_deleted)

        self.view.list_view.timesheet_selected.connect(self._on_timesheet_selected)
        self.view.detail_view.back_requested.connect(self._on_back_requested)

    def refresh(self) -> None:
        """Reset the module to list mode and refresh the list page."""
        self.view.show_list()
        self.list_presenter.refresh()

    @Slot(str)
    def _on_timesheet_selected(self, name: str) -> None:
        self.view.show_detail()
        self.detail_presenter.load_timesheet(name)

    @Slot()
    def _on_back_requested(self) -> None:
        self.view.show_list()

    @Slot()
    def _on_timesheet_deleted(self) -> None:
        self.view.show_list()
        self.list_presenter.refresh()
