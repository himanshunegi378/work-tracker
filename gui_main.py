import sys
import os
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QMetaObject, Qt, Slot, QThreadPool

from src.api import ApiClient
from src.persistence.credential_storage import CredentialStorage
from src.runtime_paths import ensure_runtime_dirs, log_file_path
from src.services.activity_service import ActivityService
from src.services.auth_service import AuthService
from src.services.project_service import ProjectService
from src.services.scheduler import CronScheduler
from src.services.timesheet_service import TimesheetService
from src.ui.activity_list_presenter import ActivityListPresenter
from src.ui.home_presenter import HomePresenter
from src.ui.settings_presenter import SettingsPresenter
from src.ui.timesheet_module_presenter import TimesheetModulePresenter
from src.ui.views.main_container import MainContainer
from src.ui.views.smart_log_dialog import SmartLogDialog
from src.ui.workers.smart_log_options_fetch_worker import SmartLogOptionsFetchWorker
from src.ui.workers.smart_log_save_worker import SmartLogSaveWorker

logger = logging.getLogger(__name__)


def configure_logging(log_path: Optional[Path] = None) -> str:
    """Configure app logging to a rotating file for later analysis."""
    resolved_log_path = Path(log_path or log_file_path())
    resolved_log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(resolved_log_path.resolve())
        for handler in root_logger.handlers
    ):
        file_handler = RotatingFileHandler(
            resolved_log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
        )
        root_logger.addHandler(file_handler)

    logger.info("Application logging configured at %s", resolved_log_path.resolve())
    return str(resolved_log_path)


class MainWindow(QMainWindow):
    """The master shell orchestrating global navigation and smart background tracking."""
    def __init__(
        self,
        auth_service: AuthService,
        project_service: ProjectService,
        activity_service: ActivityService,
        timesheet_service: TimesheetService,
    ):
        super().__init__()
        self.setWindowTitle("Senior Architect Work Tracker")
        self.setMinimumSize(850, 650)
        self.auth = auth_service
        self.project_service = project_service
        self.activity_service = activity_service
        self.timesheet_service = timesheet_service
        self._smart_log_fetch_in_flight = False
        self._smart_log_save_in_flight = False
        self._smart_log_interval_seconds = 60 * 15 # 15 minutes
        self._is_initial_prompt = False

        # 1. Initialize Background Scheduler
        self.scheduler = CronScheduler(tick_interval=5.0)

        # 2. Root Container
        self.container = MainContainer()
        self.setCentralWidget(self.container)

        # 3. Sub-Presenters & Navigation
        self.home_presenter     = HomePresenter(self.container.home_view, project_service)
        self.settings_presenter = SettingsPresenter(self.container.settings_view, self.auth)
        self.activity_presenter = ActivityListPresenter(self.container.activity_view, activity_service)
        self.timesheet_presenter = TimesheetModulePresenter(
            self.container.timesheet_view,
            timesheet_service,
        )
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
        elif module_id == "activities":
            self.container.switch_to_activities()
            self.activity_presenter.refresh()
        elif module_id == "timesheets":
            self.container.switch_to_timesheets()
            self.timesheet_presenter.refresh()
        elif module_id == "settings":
            self.container.switch_to_settings()

    def _refresh_dashboard(self):
        # Project count: use latest cached results from HomePresenter
        p_count = len(self.home_presenter.get_cached_project_names())
        timesheet_count = 0
        try:
            timesheet_count = len(self.timesheet_service.get_timesheets(page_length=20))
        except Exception:
            logger.exception("Failed to refresh dashboard timesheet stats")
            timesheet_count = 0
        self.container.dash_view.update_stats(p_count, timesheet_count)

    # --- Smart Tracker Logic ---

    def _handle_tracker_toggle(self, start: bool):
        if start:
            # Trigger smart log prompt every 30 seconds for demonstration
            self._is_initial_prompt = True # Flag to indicate the first prompt should be 0-duration
            self.scheduler.add_job(
                name="Smart Log Prompt", 
                task_func=self._trigger_gui_prompt, 
                interval_seconds=self._smart_log_interval_seconds,
                invoke_on_start=True # This will call _trigger_gui_prompt immediately
            )
            self.scheduler.start()
        else:
            self.scheduler.stop()
            self._is_initial_prompt = False

    def _trigger_gui_prompt(self):
        QMetaObject.invokeMethod(self, "show_log_prompt", Qt.QueuedConnection)

    @Slot()
    def show_log_prompt(self):
        """Fetch smart-log options off-thread, then display the dialog."""
        if self._smart_log_fetch_in_flight:
            return

        logger.info("Scheduler triggered a smart log prompt")
        worker = SmartLogOptionsFetchWorker(
            project_service=self.project_service,
            activity_service=self.activity_service,
            timesheet_service=self.timesheet_service,
            page_length=200,
        )
        worker.signals.result_ready.connect(self._on_smart_log_options_ready)
        self._smart_log_fetch_in_flight = True
        QThreadPool.globalInstance().start(worker)

    @Slot(list, list, dict, str, list)
    def _on_smart_log_options_ready(
        self,
        project_options: list,
        activity_names: list,
        smart_defaults: dict,
        activity_status_message: str,
        recent_options: list,
    ):
        """Displays SmartLogDialog after background options fetch completes."""
        self._smart_log_fetch_in_flight = False

        dialog = SmartLogDialog(
            project_options,
            activity_names,
            smart_defaults=smart_defaults,
            parent=None,
            activity_status_message=activity_status_message or None,
            recent_options=recent_options,
            is_initial=self._is_initial_prompt,
        )

        from PySide6.QtGui import QGuiApplication
        screen_geo = QGuiApplication.primaryScreen().geometry()
        dialog_geo = dialog.frameGeometry()
        dialog_geo.moveCenter(screen_geo.center())
        dialog.move(dialog_geo.topLeft())

        if dialog.exec():
            submission = dialog.get_submission()
            if submission:
                interval = 0 if self._is_initial_prompt else self._smart_log_interval_seconds
                self._save_smart_log_submission(submission, interval_seconds=interval)
        
        # Reset the flag after the prompt is dealt with (either saved or skipped)
        self._is_initial_prompt = False
        self._refresh_dashboard()

    def _save_smart_log_submission(self, submission: dict, interval_seconds: Optional[int] = None) -> None:
        """Persist the accepted smart-log payload to today's timesheet."""
        if self._smart_log_save_in_flight:
            return

        worker = SmartLogSaveWorker(
            service=self.timesheet_service,
            payload=submission,
            interval_seconds=interval_seconds if interval_seconds is not None else self._smart_log_interval_seconds,
        )
        worker.signals.result_ready.connect(self._on_smart_log_saved)
        worker.signals.error_occurred.connect(self._on_smart_log_save_error)
        self._smart_log_save_in_flight = True
        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def _on_smart_log_saved(self, detail: dict):
        """Refresh the timesheets module after one smart-log save succeeds."""
        self._smart_log_save_in_flight = False
        timesheet_item = self.container.sidebar.items.get("timesheets")
        if timesheet_item and timesheet_item.property("active") == "true":
            self.timesheet_presenter.refresh()

    @Slot(str)
    def _on_smart_log_save_error(self, message: str):
        """Surface smart-log save failures after the dialog has closed."""
        self._smart_log_save_in_flight = False
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Smart Log Save Failed", message)

    def closeEvent(self, event):
        self.scheduler.stop()
        event.accept()

def main():
    ensure_runtime_dirs()
    log_path = configure_logging()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Initialize API and Auth / Service Layer
    api_client       = ApiClient(base_url="https://matrix.samta.ai")
    cred_storage     = CredentialStorage()
    auth_service     = AuthService(api_client, cred_storage)
    project_service  = ProjectService(api_client)
    activity_service = ActivityService(api_client)
    timesheet_service = TimesheetService(api_client, auth_service)

    window = MainWindow(
        auth_service,
        project_service,
        activity_service,
        timesheet_service,
    )
    window.show()
    logger.info("Main window launched; analysis log file: %s", Path(log_path).resolve())
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
