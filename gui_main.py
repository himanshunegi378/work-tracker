import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QMetaObject, Qt, Slot

# Add src to python path for modular imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from services.project_manager import ProjectManager
from services.log_manager import LogManager
from services.scheduler import CronScheduler
from persistence.storage import JSONStorage
from ui.views.main_container import MainContainer
from ui.home_presenter import HomePresenter
from ui.views.smart_log_dialog import SmartLogDialog

class MainWindow(QMainWindow):
    """The master shell orchestrating global navigation and smart background tracking."""
    def __init__(self, project_manager: ProjectManager, log_manager: LogManager):
        super().__init__()
        self.setWindowTitle("Senior Architect Work Tracker")
        self.setMinimumSize(850, 650)
        self.pm = project_manager
        self.lm = log_manager

        # 1. Initialize Background Scheduler
        self.scheduler = CronScheduler(tick_interval=5.0)

        # 2. Root Container
        self.container = MainContainer()
        self.setCentralWidget(self.container)

        # 3. Sub-Presenters & Navigation
        self.home_presenter = HomePresenter(self.container.home_view, self.pm)
        self.container.sidebar.nav_requested.connect(self._handle_navigation)
        self.container.dash_view.tracker_toggle_requested.connect(self._handle_tracker_toggle)

        # 4. Initial Screen
        self._handle_navigation("home")

    def _handle_navigation(self, module_id: str):
        if module_id == "home":
            self.container.switch_to_home()
            self._refresh_dashboard()
        elif module_id == "projects":
            self.container.switch_to_projects()
            self.home_presenter.refresh_projects()
        elif module_id == "logs":
            self.container.switch_to_logs()
            self._refresh_logs()

    def _refresh_dashboard(self):
        p_count = len(self.pm.get_all_projects())
        l_count = len(self.lm.get_all_logs())
        self.container.dash_view.update_stats(p_count, l_count)

    def _refresh_logs(self):
        logs = self.lm.get_all_logs()
        self.container.log_view.display_logs(logs)

    # --- Smart Tracker Logic ---

    def _handle_tracker_toggle(self, start: bool):
        if start:
            # Trigger smart log prompt every 30 seconds for demonstration
            self.scheduler.add_job(
                name="Smart Log Prompt", 
                task_func=self._trigger_gui_prompt, 
                interval_seconds=30
            )
            self.scheduler.start()
        else:
            self.scheduler.stop()

    def _trigger_gui_prompt(self):
        QMetaObject.invokeMethod(self, "show_log_prompt", Qt.QueuedConnection)

    @Slot()
    def show_log_prompt(self):
        """Displays the SmartLogDialog with pre-filled defaults. Shows even if minimized."""
        print("🕒 Scheduler triggered a SMART GUI log prompt.")
        
        # Architecture: Passing None as parent makes this dialog its own top-level window
        # This ensures it shows up even if MainWindow is minimized.
        dialog = SmartLogDialog(self.pm, self.lm, parent=None)
        
        # Center the dialog manually if no parent is provided
        from PySide6.QtGui import QGuiApplication
        screen_geo = QGuiApplication.primaryScreen().geometry()
        dialog_geo = dialog.frameGeometry()
        dialog_geo.moveCenter(screen_geo.center())
        dialog.move(dialog_geo.topLeft())
        
        dialog.exec()
        self._refresh_dashboard()

    def closeEvent(self, event):
        self.scheduler.stop()
        event.accept()

def main():
    if not os.path.exists("data"):
        os.makedirs("data")
        
    p_storage = JSONStorage("data/projects.json")
    l_storage = JSONStorage("data/logs.json")
    
    p_manager = ProjectManager(p_storage)
    l_manager = LogManager(l_storage)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow(p_manager, l_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
