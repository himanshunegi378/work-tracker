import argparse
import os
import sys
import logging
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QTimer, Slot, QThreadPool

from src.core import ipc, prefs
from src.core.app import build_app
from src.core.logging_setup import configure_logging
from src.runtime_paths import ensure_runtime_dirs, user_data_dir
from src.services.activity_service import ActivityService
from src.services.auth_service import AuthService
from src.services.project_service import ProjectService
from src.services.timesheet_service import TimesheetService
from src.ui.design import apply_theme
from src.ui.ipc_server import IpcServer
from src.ui.single_instance import SingleInstance
from src.ui.tracker_controller import TrackerController
from src.ui.tray import TrayController
from src.ui.activity_list_presenter import ActivityListPresenter
from src.ui.home_presenter import HomePresenter
from src.ui.settings_presenter import SettingsPresenter
from src.ui.timesheet_module_presenter import TimesheetModulePresenter
from src.ui.views.main_container import MainContainer
from src.ui.views.smart_log_dialog import SmartLogDialog
from src.ui.workers.smart_log_options_fetch_worker import SmartLogOptionsFetchWorker
from src.ui.workers.smart_log_save_worker import SmartLogSaveWorker

logger = logging.getLogger(__name__)


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
        self._quitting = False
        self._tray_notice_shown = False
        self.started_hidden = False   # launched with --hidden (e.g. by `samta-tracker start`)
        self._window_shown = False    # the user has seen the window at least once

        # 1. Reminder tracker (shared by the dashboard button, tray icon and CLI)
        self.tracker = TrackerController(parent=self)
        self.tracker.prompt_requested.connect(self.show_log_prompt)
        self.tracker.state_changed.connect(self._on_tracker_state_changed)
        self.tray: Optional[TrayController] = None

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
            project_service=project_service,
            activity_service=activity_service,
        )
        self.timesheet_presenter.data_changed.connect(self._refresh_dashboard)
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
        """Dashboard button handler."""
        try:
            self.tracker.start() if start else self.tracker.stop()
        except ValueError as exc:
            QMessageBox.warning(self, "Tracker", str(exc))

    def _on_tracker_state_changed(self, active: bool):
        """Keep the dashboard button and tray menu in step with the real tracker state."""
        self.container.dash_view.set_tracking(active)
        if self.tray:
            self.tray.set_tracking(active)

    # --- Tray, window and CLI control ---

    def setup_tray(self) -> bool:
        """Create the tray icon when the desktop has one. Returns whether it is available."""
        if not TrayController.available():
            return False
        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_window)
        self.tray.toggle_tracker_requested.connect(
            lambda: self.tracker.stop() if self.tracker.active else self.tracker.start()
        )
        self.tray.quit_requested.connect(self.quit_app)
        self.tray.set_tracking(self.tracker.active)
        self.tray.show()
        return True

    def showEvent(self, event):
        self._window_shown = True
        super().showEvent(event)

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._quitting = True
        self.tracker.stop()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def handle_ipc(self, cmd: str, args: dict) -> dict:
        """Run one CLI command. Called on the GUI thread by the IPC server."""
        if cmd == "ping":
            return {"pid": os.getpid()}
        if cmd == "window.show":
            self.show_window()
            return {}
        if cmd == "tracker.status":
            return self.status()
        if cmd == "tracker.start":
            every = args.get("every")
            if every is not None and (isinstance(every, bool) or not isinstance(every, int)):
                raise ipc.IpcCommandError("'every' must be a whole number of seconds.")
            try:
                self.tracker.start(every)
            except ValueError as exc:
                raise ipc.IpcCommandError(str(exc)) from exc
            return self.status()
        if cmd == "tracker.stop":
            self.tracker.stop()
            return self.status()
        if cmd == "data.refresh":
            self._refresh_dashboard()
            timesheet_item = self.container.sidebar.items.get("timesheets")
            if timesheet_item and timesheet_item.property("active") == "true":
                self.timesheet_presenter.refresh()
            return {}
        if cmd == "app.quit":
            # reply first, then quit on the next event-loop turn
            QTimer.singleShot(100, self.quit_app)
            return {}
        raise ipc.IpcCommandError(f"Unknown command '{cmd}'.")

    def status(self) -> dict:
        return {
            "pid": os.getpid(),
            "tracker": self.tracker.status(),
            "window_visible": self.isVisible() and not self.isMinimized(),
            "tray": self.tray is not None,
            "started_hidden": self.started_hidden,
            "window_shown": self._window_shown,
        }

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
            is_initial=self.tracker.initial_prompt,
        )

        from PySide6.QtGui import QGuiApplication
        screen_geo = QGuiApplication.primaryScreen().geometry()
        dialog_geo = dialog.frameGeometry()
        dialog_geo.moveCenter(screen_geo.center())
        dialog.move(dialog_geo.topLeft())

        if dialog.exec():
            submission = dialog.get_submission()
            if submission:
                interval = 0 if self.tracker.initial_prompt else self.tracker.interval_seconds
                self._save_smart_log_submission(submission, interval_seconds=interval)
        
        # Reset the flag after the prompt is dealt with (either saved or skipped)
        self.tracker.initial_prompt = False
        self._refresh_dashboard()

    def _save_smart_log_submission(self, submission: dict, interval_seconds: Optional[int] = None) -> None:
        """Persist the accepted smart-log payload to today's timesheet."""
        if self._smart_log_save_in_flight:
            return

        worker = SmartLogSaveWorker(
            service=self.timesheet_service,
            payload=submission,
            interval_seconds=interval_seconds if interval_seconds is not None else self.tracker.interval_seconds,
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
        """With a tray icon, closing the window hides it to the tray; Quit in the tray menu exits."""
        if not self._quitting and self.tray is not None:
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self._tray_notice_shown = True
                self.tray.notify("Work Tracker", "Still running in the tray. Right-click the tray icon to quit.")
            return
        self.quit_app()
        event.accept()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="work-tracker-gui", add_help=True)
    parser.add_argument("--hidden", action="store_true",
                        help="start in the system tray without showing the window")
    args, _ = parser.parse_known_args(argv)  # leave Qt's own options alone
    return args


def main(argv=None):
    args = parse_args(argv)
    ensure_runtime_dirs()
    log_path = configure_logging()

    # Only one app per user: hand over to the running one instead of opening a second.
    instance = SingleInstance(user_data_dir() / "gui.lock")
    if not instance.acquire():
        logger.info("Another instance is running; asking it to show its window")
        if ipc.wait_until_running(timeout=3.0):
            try:
                ipc.request("window.show")
            except (ipc.IpcUnavailable, ipc.IpcError):
                logger.warning("Could not reach the running instance")
        return 0

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)  # we decide when to quit (tray, dialogs)
    apply_theme(app)

    # Shared service graph (same wiring the CLI uses)
    ctx = build_app()

    window = MainWindow(
        ctx.auth,
        ctx.projects,
        ctx.activities,
        ctx.timesheets,
    )
    window.started_hidden = args.hidden
    has_tray = window.setup_tray()

    server = IpcServer(window.handle_ipc, parent=window)
    if not server.start():
        logger.error("CLI control is unavailable (could not open the local socket)")
    app.aboutToQuit.connect(server.stop)

    if args.hidden and has_tray:
        logger.info("Started hidden in the tray")
    elif args.hidden:
        logger.info("No system tray available; starting minimized instead")
        window.showMinimized()
    else:
        window.show()
    logger.info("Main window launched; analysis log file: %s", Path(log_path).resolve())

    try:
        return app.exec()
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
