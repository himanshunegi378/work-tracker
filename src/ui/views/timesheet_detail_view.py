"""
timesheet_detail_view.py
------------------------
Pure View component for the Timesheet detail page.
"""
from typing import Dict, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_COLORS = {
    "bg": "#F5F7FA",
    "card": "#FFFFFF",
    "border": "#E0E0E0",
    "primary": "#2196F3",
    "primary_hover": "#1976D2",
    "text_dark": "#263238",
    "text_muted": "#78909C",
    "disabled": "#B0BEC5",
}

_BTN_STYLE = f"""
    QPushButton {{
        background-color: {_COLORS['primary']};
        color: white;
        padding: 8px 18px;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {_COLORS['primary_hover']};
    }}
    QPushButton:disabled {{
        background-color: {_COLORS['disabled']};
    }}
"""

_TABLE_STYLE = f"""
    QTableWidget {{
        border: none;
        background: white;
        gridline-color: {_COLORS['border']};
        font-size: 13px;
        color: {_COLORS['text_dark']};
    }}
    QHeaderView::section {{
        background-color: #ECEFF1;
        color: {_COLORS['text_muted']};
        font-size: 11px;
        font-weight: bold;
        padding: 8px 12px;
        border: none;
        border-bottom: 2px solid {_COLORS['border']};
    }}
"""


class TimesheetDetailView(QWidget):
    """UI component for rendering one timesheet detail payload."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._summary_labels: Dict[str, QLabel] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(16)
        self.setStyleSheet(f"background-color: {_COLORS['bg']};")

        header_row = QHBoxLayout()
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet(_BTN_STYLE)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_btn)

        self.title_lbl = QLabel("Timesheet Detail")
        self.title_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {_COLORS['text_dark']};"
        )
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()
        main_layout.addLayout(header_row)

        summary_card = QFrame()
        summary_card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {_COLORS['card']};
                border: 1px solid {_COLORS['border']};
                border-radius: 10px;
            }}
            """
        )
        summary_layout = QGridLayout(summary_card)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setHorizontalSpacing(18)
        summary_layout.setVerticalSpacing(12)

        summary_fields = [
            ("Timesheet", "name"),
            ("Workflow", "workflow_state"),
            ("Status", "status"),
            ("Employee", "employee_name"),
            ("Department", "department"),
            ("Company", "company"),
            ("Start Date", "start_date"),
            ("End Date", "end_date"),
            ("Total Hours", "total_hours"),
            ("Billable Hours", "total_billable_hours"),
            ("Currency", "currency"),
        ]
        for index, (label_text, key) in enumerate(summary_fields):
            row = index // 2
            col = (index % 2) * 2
            label = QLabel(f"{label_text}:")
            label.setStyleSheet(f"font-size: 12px; color: {_COLORS['text_muted']};")
            value = QLabel("—")
            value.setStyleSheet(f"font-size: 13px; color: {_COLORS['text_dark']};")
            value.setWordWrap(True)
            summary_layout.addWidget(label, row, col)
            summary_layout.addWidget(value, row, col + 1)
            self._summary_labels[key] = value

        main_layout.addWidget(summary_card)

        logs_card = QFrame()
        logs_card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {_COLORS['card']};
                border: 1px solid {_COLORS['border']};
                border-radius: 10px;
            }}
            """
        )
        logs_layout = QVBoxLayout(logs_card)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(0)

        self.time_logs_table = QTableWidget(0, 7)
        self.time_logs_table.setHorizontalHeaderLabels(
            ["Activity", "Project", "From", "To", "Hours", "Billable", "Description"]
        )
        self.time_logs_table.setStyleSheet(_TABLE_STYLE)
        self.time_logs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.time_logs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.time_logs_table.verticalHeader().setVisible(False)
        for column in range(7):
            mode = QHeaderView.Stretch if column in (1, 6) else QHeaderView.ResizeToContents
            self.time_logs_table.horizontalHeader().setSectionResizeMode(column, mode)
        self.time_logs_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        logs_layout.addWidget(self.time_logs_table)

        self.loading_lbl = QLabel("  Loading…")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        self.loading_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 14px; padding: 30px;"
        )
        self.loading_lbl.hide()
        logs_layout.addWidget(self.loading_lbl)

        self.empty_lbl = QLabel("No time logs found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 13px; padding: 40px;"
        )
        self.empty_lbl.hide()
        logs_layout.addWidget(self.empty_lbl)

        main_layout.addWidget(logs_card, stretch=1)

    @Slot(dict)
    def display_timesheet_detail(self, detail: dict) -> None:
        """Render one normalized timesheet detail payload."""
        self.title_lbl.setText(f"Timesheet Detail • {detail.get('name') or '—'}")
        for key, label in self._summary_labels.items():
            value = detail.get(key)
            label.setText("—" if value in (None, "") else str(value))

        self.time_logs_table.setRowCount(0)
        time_logs: List[dict] = detail.get("time_logs") or []
        if not time_logs:
            self.empty_lbl.show()
            self.time_logs_table.hide()
            return

        self.empty_lbl.hide()
        self.time_logs_table.show()
        for log in time_logs:
            row = self.time_logs_table.rowCount()
            self.time_logs_table.insertRow(row)
            values = [
                str(log.get("activity_type", "—")),
                str(log.get("project_name") or log.get("project") or "—"),
                str(log.get("from_time", "—")),
                str(log.get("to_time", "—")),
                str(log.get("hours", "—")),
                "Yes" if log.get("is_billable") else "No",
                str(log.get("description", "")),
            ]
            for column, value in enumerate(values):
                self.time_logs_table.setItem(row, column, QTableWidgetItem(value))

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        """Shows/hides the loading indicator and disables interactive controls."""
        self.back_btn.setEnabled(not is_loading)
        if is_loading:
            self.time_logs_table.hide()
            self.empty_lbl.hide()
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()

    @Slot(str)
    def show_error(self, message: str) -> None:
        """Displays a modal error dialog to the user."""
        QMessageBox.critical(self, "Error Fetching Timesheet Detail", message)
