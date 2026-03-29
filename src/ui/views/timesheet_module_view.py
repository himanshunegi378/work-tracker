"""
timesheet_module_view.py
------------------------
Container view for list/detail navigation within the Timesheets module.
"""
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from src.ui.views.timesheet_detail_view import TimesheetDetailView
from src.ui.views.timesheet_list_view import TimesheetListView


class TimesheetModuleView(QWidget):
    """Owns the list/detail stacked views for the Timesheets module."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.list_view = TimesheetListView()
        self.detail_view = TimesheetDetailView()

        self.stack.addWidget(self.list_view)
        self.stack.addWidget(self.detail_view)
        layout.addWidget(self.stack)

    def show_list(self) -> None:
        self.stack.setCurrentWidget(self.list_view)

    def show_detail(self) -> None:
        self.stack.setCurrentWidget(self.detail_view)
