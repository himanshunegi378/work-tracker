from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from PySide6.QtCore import Signal

from src.ui.design import SPACE, Card, StatCard, button, label, set_prop


class DashboardView(QWidget):
    """The landing page providing an overview and tracker control."""
    tracker_toggle_requested = Signal(bool)  # Emits True to start, False to stop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_tracking = False
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(SPACE["xl"])

        self.layout.addWidget(label("Welcome back, Architect", "display"))

        # Tracker control card
        self.tracker_frame = Card()
        row = QHBoxLayout()
        info = QVBoxLayout()
        info.setSpacing(SPACE["xs"])
        self.tracker_title = label("Work Tracker: INACTIVE", "heading")
        info.addWidget(self.tracker_title)
        info.addWidget(label(
            "Start the background tracker to receive periodic log reminders.", "caption"))

        self.start_btn = button("START TRACKER", "primary")
        self.start_btn.setFixedWidth(150)
        self.start_btn.clicked.connect(self._on_tracker_clicked)

        row.addLayout(info)
        row.addStretch()
        row.addWidget(self.start_btn)
        self.tracker_frame.body.addLayout(row)
        self.layout.addWidget(self.tracker_frame)

        # Stats
        self.layout.addWidget(label("Overview", "heading"))
        stats = QHBoxLayout()
        stats.setSpacing(SPACE["lg"])
        self.project_stat = StatCard("Total Projects", "0", "accent")
        self.log_stat = StatCard("Timesheet Rows", "0", "success")
        stats.addWidget(self.project_stat)
        stats.addWidget(self.log_stat)
        self.layout.addLayout(stats)
        self.layout.addStretch()

    def _on_tracker_clicked(self):
        self._is_tracking = not self._is_tracking
        self.tracker_toggle_requested.emit(self._is_tracking)
        self._update_ui_state()

    def _update_ui_state(self):
        active = self._is_tracking
        self.tracker_title.setText("Work Tracker: ACTIVE" if active else "Work Tracker: INACTIVE")
        set_prop(self.tracker_title, "tone", "success" if active else "")
        self.start_btn.setText("STOP TRACKER" if active else "START TRACKER")
        set_prop(self.start_btn, "variant", "danger" if active else "primary")

    def update_stats(self, project_count: int, log_count: int):
        self.project_stat.set_value(project_count)
        self.log_stat.set_value(log_count)
