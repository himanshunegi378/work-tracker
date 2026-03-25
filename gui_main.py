import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QMetaObject, Qt, Slot, QThreadPool

# Add src to python path for modular imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from services.log_manager import LogManager
from services.scheduler import CronScheduler
from services.activity_service import ActivityService
from services.project_service import ProjectService
from persistence.storage import JSONStorage
from ui.views.main_container import MainContainer
from ui.home_presenter import HomePresenter
from ui.views.smart_log_dialog import SmartLogDialog
from ui.settings_presenter import SettingsPresenter
from ui.activity_list_presenter import ActivityListPresenter
from ui.workers.smart_log_options_fetch_worker import SmartLogOptionsFetchWorker
from api import ApiClient
from services.auth_service import AuthService
from persistence.credential_storage import CredentialStorage

class MainWindow(QMainWindow):
    """The master shell orchestrating global navigation and smart background tracking."""
    def __init__(
        self,
        log_manager: LogManager,
        auth_service: AuthService,
        project_service: ProjectService,
        activity_service: ActivityService,
    ):
        super().__init__()
        self.setWindowTitle("Senior Architect Work Tracker")
        self.setMinimumSize(850, 650)
        self.lm   = log_manager
        self.auth = auth_service
        self.project_service = project_service
        self.activity_service = activity_service
        self._smart_log_fetch_in_flight = False

        # 1. Initialize Background Scheduler
        self.scheduler = CronScheduler(tick_interval=5.0)

        # 2. Root Container
        self.container = MainContainer()
        self.setCentralWidget(self.container)

        # 3. Sub-Presenters & Navigation
        self.home_presenter     = HomePresenter(self.container.home_view, project_service)
        self.settings_presenter = SettingsPresenter(self.container.settings_view, self.auth)
        self.activity_presenter = ActivityListPresenter(self.container.activity_view, activity_service)
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
        elif module_id == "activities":
            self.container.switch_to_activities()
            self.activity_presenter.refresh()
        elif module_id == "settings":
            self.container.switch_to_settings()

    def _refresh_dashboard(self):
        # Project count: use latest cached results from HomePresenter
        p_count = len(self.home_presenter.get_cached_project_names())
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
                interval_seconds=10
            )
            self.scheduler.start()
        else:
            self.scheduler.stop()

    def _trigger_gui_prompt(self):
        QMetaObject.invokeMethod(self, "show_log_prompt", Qt.QueuedConnection)

    @Slot()
    def show_log_prompt(self):
        """Fetch smart-log options off-thread, then display the dialog."""
        if self._smart_log_fetch_in_flight:
            return

        print("🕒 Scheduler triggered a SMART GUI log prompt.")
        worker = SmartLogOptionsFetchWorker(
            project_service=self.project_service,
            activity_service=self.activity_service,
            page_length=200,
        )
        worker.signals.result_ready.connect(self._on_smart_log_options_ready)
        self._smart_log_fetch_in_flight = True
        QThreadPool.globalInstance().start(worker)

    @Slot(list, list, str)
    def _on_smart_log_options_ready(
        self,
        project_names: list,
        activity_names: list,
        activity_status_message: str,
    ):
        """Displays SmartLogDialog after background options fetch completes."""
        self._smart_log_fetch_in_flight = False

        dialog = SmartLogDialog(
            project_names,
            activity_names,
            self.lm,
            parent=None,
            activity_status_message=activity_status_message or None,
        )

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

    # Logs only (projects now come from API)
    l_storage = JSONStorage("data/logs.json")
    l_manager = LogManager(l_storage)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Initialize API and Auth / Service Layer
    api_client       = ApiClient(base_url="https://matrix.samta.ai")
    cred_storage     = CredentialStorage("data/credentials.json")
    auth_service     = AuthService(api_client, cred_storage)
    project_service  = ProjectService(api_client)
    activity_service = ActivityService(api_client)

    window = MainWindow(l_manager, auth_service, project_service, activity_service)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
