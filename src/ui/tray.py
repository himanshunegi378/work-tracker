"""System tray icon: Open / Start-Stop tracker / Quit."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.ui.design import current, manager
from src.ui.icons import make_icon


class TrayController(QObject):
    open_requested = Signal()
    toggle_tracker_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(self._icon(), parent)
        self._tray.setToolTip("Work Tracker")
        menu = QMenu()
        self._open = QAction("Open Work Tracker", menu)
        self._toggle = QAction("Start tracker", menu)
        self._quit = QAction("Quit", menu)
        for action in (self._open, self._toggle):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self._quit)
        self._menu = menu  # keep a reference so it isn't garbage collected
        self._tray.setContextMenu(menu)
        self._open.triggered.connect(self.open_requested)
        self._toggle.triggered.connect(self.toggle_tracker_requested)
        self._quit.triggered.connect(self.quit_requested)
        self._tray.activated.connect(self._on_activated)
        manager.changed.connect(lambda _t: self._tray.setIcon(self._icon()))

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    @staticmethod
    def _icon() -> QIcon:
        return make_icon("timesheets", current().accent, 64)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_tracking(self, active: bool) -> None:
        self._toggle.setText("Stop tracker" if active else "Start tracker")
        self._tray.setToolTip("Work Tracker: tracking" if active else "Work Tracker")

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, 4000)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_requested.emit()
