from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QStackedWidget
)
from ui.views.sidebar_view import SidebarView
from ui.views.dashboard_view import DashboardView
from ui.views.home_view import HomeView
from ui.views.log_view import LogView

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
        self.log_view = LogView()

        self.stack.addWidget(self.dash_view)  # Index 0
        self.stack.addWidget(self.home_view)  # Index 1
        self.stack.addWidget(self.log_view)   # Index 2

    def switch_to_home(self):
        self.stack.setCurrentIndex(0)
        self.sidebar.set_active("home")

    def switch_to_projects(self):
        self.stack.setCurrentIndex(1)
        self.sidebar.set_active("projects")

    def switch_to_logs(self):
        self.stack.setCurrentIndex(2)
        self.sidebar.set_active("logs")
