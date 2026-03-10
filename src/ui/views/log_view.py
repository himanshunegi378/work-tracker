from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from models.log import Log
from typing import List

class LogView(QWidget):
    """Displays a chronological list of activity logs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Activity Logs")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333; margin-bottom: 15px;")
        self.layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        
        self.scroll.setWidget(self.list_container)
        self.layout.addWidget(self.scroll)

    def display_logs(self, logs: List[Log]):
        """Renders the list of log entries."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not logs:
            empty = QLabel("No logs recorded yet.")
            empty.setStyleSheet("color: #999; margin-top: 50px;")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
            return

        # Sort logs by timestamp descending (newest first)
        sorted_logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)

        for l in sorted_logs:
            card = self._create_log_item(l)
            self.list_layout.addWidget(card)

    def _create_log_item(self, log: Log) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(5)

        # Meta info row
        meta = QLabel(f"[{log.timestamp[:19].replace('T', ' ')}]  <b>{log.project_name}</b>")
        meta.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(meta)

        desc = QLabel(log.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #424242;")
        layout.addWidget(desc)

        return frame
