"""
timesheet_list_view.py
----------------------
Pure View component for the Timesheet List page.
"""
import logging
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
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

logger = logging.getLogger(__name__)

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

_TABLE_STYLE = f"""
    QTableWidget {{
        border: none;
        background: white;
        gridline-color: {_COLORS['border']};
        font-size: 13px;
        color: {_COLORS['text_dark']};
    }}
    QTableWidget::item {{
        padding: 8px 12px;
    }}
    QTableWidget::item:selected {{
        background-color: #E3F2FD;
        color: {_COLORS['text_dark']};
    }}
    QHeaderView::section {{
        background-color: #ECEFF1;
        color: {_COLORS['text_muted']};
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 0.5px;
        padding: 8px 12px;
        border: none;
        border-bottom: 2px solid {_COLORS['border']};
    }}
"""

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

_NAV_BTN_STYLE = f"""
    QPushButton {{
        background-color: white;
        color: {_COLORS['primary']};
        padding: 6px 14px;
        border: 1px solid {_COLORS['primary']};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #E3F2FD;
    }}
    QPushButton:disabled {{
        color: {_COLORS['disabled']};
        border-color: {_COLORS['disabled']};
        background-color: white;
    }}
"""


class TimesheetListView(QWidget):
    """UI component for browsing Timesheets fetched from the backend."""

    fetch_requested = Signal(int)
    timesheet_selected = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._current_page: int = 0
        self._page_size: int = 20
        self._row_timesheet_names: List[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(16)
        self.setStyleSheet(f"background-color: {_COLORS['bg']};")

        header_row = QHBoxLayout()

        header_lbl = QLabel("⏱️ Timesheets")
        header_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {_COLORS['text_dark']};"
        )
        header_row.addWidget(header_lbl)
        header_row.addStretch()

        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.setStyleSheet(_BTN_STYLE)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_row.addWidget(self.refresh_btn)

        main_layout.addLayout(header_row)

        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {_COLORS['card']};
                border: 1px solid {_COLORS['border']};
                border-radius: 10px;
            }}
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Workflow State", "Status", "Start Date", "End Date", "Total Hours"]
        )
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.itemClicked.connect(self._on_item_clicked)
        self.table.verticalHeader().setVisible(False)
        for column in range(6):
            mode = QHeaderView.Stretch if column == 0 else QHeaderView.ResizeToContents
            self.table.horizontalHeader().setSectionResizeMode(column, mode)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.table)

        self.loading_lbl = QLabel("  Loading…")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        self.loading_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 14px; padding: 30px;"
        )
        self.loading_lbl.hide()
        card_layout.addWidget(self.loading_lbl)

        self.empty_lbl = QLabel("No timesheets found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 13px; padding: 40px;"
        )
        self.empty_lbl.hide()
        card_layout.addWidget(self.empty_lbl)

        main_layout.addWidget(card, stretch=1)

        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(10)

        self.prev_btn = QPushButton("← Prev")
        self.prev_btn.setStyleSheet(_NAV_BTN_STYLE)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev_clicked)
        pagination_row.addWidget(self.prev_btn)

        self.page_lbl = QLabel("Page 1")
        self.page_lbl.setStyleSheet(f"font-size: 12px; color: {_COLORS['text_muted']};")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        pagination_row.addWidget(self.page_lbl)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet(_NAV_BTN_STYLE)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_clicked)
        pagination_row.addWidget(self.next_btn)

        pagination_row.addStretch()

        self.result_count_lbl = QLabel("")
        self.result_count_lbl.setStyleSheet(
            f"font-size: 12px; color: {_COLORS['text_muted']};"
        )
        pagination_row.addWidget(self.result_count_lbl)

        main_layout.addLayout(pagination_row)

    def _on_refresh_clicked(self) -> None:
        self._current_page = 0
        self.fetch_requested.emit(self._current_page)

    def _on_prev_clicked(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.fetch_requested.emit(self._current_page)

    def _on_next_clicked(self) -> None:
        self._current_page += 1
        self.fetch_requested.emit(self._current_page)

    def _on_item_clicked(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if 0 <= row < len(self._row_timesheet_names):
            self.timesheet_selected.emit(self._row_timesheet_names[row])

    @Slot(list)
    def display_timesheets(self, timesheets: List[Dict[str, Any]]) -> None:
        """Populates the table with the fetched timesheet list."""
        self.table.setRowCount(0)
        self._row_timesheet_names = []
        self.loading_lbl.hide()

        if not timesheets:
            self.empty_lbl.show()
            self.table.hide()
            return

        self.empty_lbl.hide()
        self.table.show()

        for timesheet in timesheets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_timesheet_names.append(str(timesheet.get("name", "")))
            values = [
                str(timesheet.get("name", "—")),
                str(timesheet.get("workflow_state", "—")),
                str(timesheet.get("status", "—")),
                str(timesheet.get("start_date", "—")),
                str(timesheet.get("end_date", "—")),
                str(timesheet.get("total_hours", "—")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 5:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        """Shows/hides the loading indicator and disables interactive controls."""
        self.refresh_btn.setEnabled(not is_loading)
        self.prev_btn.setEnabled(not is_loading)
        self.next_btn.setEnabled(not is_loading)
        self.table.setEnabled(not is_loading)

        if is_loading:
            self.table.hide()
            self.empty_lbl.hide()
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()

    @Slot(int, int, int)
    def set_page_info(self, current_page: int, page_size: int, result_count: int) -> None:
        """Updates pagination controls and result count labels."""
        self._current_page = current_page
        self._page_size = page_size

        self.page_lbl.setText(f"Page {current_page + 1}")
        self.prev_btn.setEnabled(current_page > 0)
        self.next_btn.setEnabled(result_count >= page_size)

        start = current_page * page_size + 1
        end = current_page * page_size + result_count
        if result_count > 0:
            self.result_count_lbl.setText(f"Showing {start}–{end} results")
        else:
            self.result_count_lbl.setText("No results")

    @Slot(str)
    def show_error(self, message: str) -> None:
        """Displays a modal error dialog to the user."""
        QMessageBox.critical(self, "Error Fetching Timesheets", message)
