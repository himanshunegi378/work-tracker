from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QStackedWidget
)
from src.ui.views.activity_list_view import ActivityListView
from src.ui.views.dashboard_view import DashboardView
from src.ui.views.home_view import HomeView
from src.ui.views.settings_view import SettingsView
from src.ui.views.sidebar_view import SidebarView
from src.ui.views.timesheet_module_view import TimesheetModuleView

class MainContainer(QWidget):
    """The root container orchestrating the sidebar and stacked content area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Sidebar
        self.sidebar = SidebarView()
        self.layout.addWidget(self.sidebar)

        # 2. Stacked Content Area
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # 3. Views
        self.dash_view = DashboardView()
        self.home_view = HomeView()  # This serves as the Projects List
        self.settings_view = SettingsView()
        self.activity_view = ActivityListView()
        self.timesheet_view = TimesheetModuleView()

        self.stack.addWidget(self.dash_view)       # Index 0
        self.stack.addWidget(self.home_view)       # Index 1
        self.stack.addWidget(self.settings_view)   # Index 2
        self.stack.addWidget(self.activity_view)   # Index 3
        self.stack.addWidget(self.timesheet_view)  # Index 4

    def switch_to_home(self):
        self.stack.setCurrentIndex(0)
        self.sidebar.set_active("home")

    def switch_to_projects(self):
        self.stack.setCurrentIndex(1)
        self.sidebar.set_active("projects")

    def switch_to_settings(self):
        self.stack.setCurrentIndex(2)
        self.sidebar.set_active("settings")

    def switch_to_activities(self):
        self.stack.setCurrentIndex(3)
        self.sidebar.set_active("activities")

    def switch_to_timesheets(self):
        self.stack.setCurrentIndex(4)
        self.sidebar.set_active("timesheets")
