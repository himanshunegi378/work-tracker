from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal

class StatCard(QFrame):
    """A small widget to display a single metric (e.g., Total Projects)."""
    def __init__(self, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 15px;
            }}
            QLabel#title {{ color: #757575; font-size: 12px; font-weight: bold; }}
            QLabel#value {{ color: {color}; font-size: 28px; font-weight: bold; }}
        """)
        
        layout = QVBoxLayout(self)
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("title")
        value_lbl = QLabel(value)
        value_lbl.setObjectName("value")
        
        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)

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
        self.layout.setSpacing(25)

        # Welcome Section
        welcome_lbl = QLabel("Welcome back, Architect")
        welcome_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #263238;")
        self.layout.addWidget(welcome_lbl)

        # Tracker Control Card
        self.tracker_frame = QFrame()
        self.tracker_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        tracker_layout = QHBoxLayout(self.tracker_frame)
        
        tracker_info = QVBoxLayout()
        self.tracker_title = QLabel("Work Tracker: INACTIVE")
        self.tracker_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #757575;")
        
        tracker_desc = QLabel("Start the background tracker to receive periodic log reminders.")
        tracker_desc.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        
        tracker_info.addWidget(self.tracker_title)
        tracker_info.addWidget(tracker_desc)
        
        self.start_btn = QPushButton("START TRACKER")
        self.start_btn.setFixedWidth(150)
        self._update_button_style(False)
        self.start_btn.clicked.connect(self._on_tracker_clicked)
        
        tracker_layout.addLayout(tracker_info)
        tracker_layout.addStretch()
        tracker_layout.addWidget(self.start_btn)
        
        self.layout.addWidget(self.tracker_frame)

        # Stats Grid
        stats_header = QLabel("Overview")
        stats_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #455A64; margin-top: 10px;")
        self.layout.addWidget(stats_header)

        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(15)
        
        self.project_stat = StatCard("Total Projects", "0", "#2196F3")
        self.log_stat = StatCard("Timesheet Rows", "0", "#4CAF50")
        
        self.stats_layout.addWidget(self.project_stat)
        self.stats_layout.addWidget(self.log_stat)
        self.stats_layout.addStretch()
        
        self.layout.addLayout(self.stats_layout)
        self.layout.addStretch()

    def _on_tracker_clicked(self):
        self._is_tracking = not self._is_tracking
        self.tracker_toggle_requested.emit(self._is_tracking)
        self._update_ui_state()

    def _update_ui_state(self):
        if self._is_tracking:
            self.tracker_title.setText("Work Tracker: ACTIVE 🚀")
            self.tracker_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50;")
            self.start_btn.setText("STOP TRACKER")
            self._update_button_style(True)
        else:
            self.tracker_title.setText("Work Tracker: INACTIVE")
            self.tracker_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #757575;")
            self.start_btn.setText("START TRACKER")
            self._update_button_style(False)

    def _update_button_style(self, active: bool):
        if active:
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    border-radius: 8px;
                    padding: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #D32F2F; }
            """)
        else:
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border-radius: 8px;
                    padding: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #1976D2; }
            """)

    def update_stats(self, project_count: int, log_count: int):
        self.project_stat.findChild(QLabel, "value").setText(str(project_count))
        self.log_stat.findChild(QLabel, "value").setText(str(log_count))
