"""
timesheet_list_view.py
----------------------
Pure View component for the Timesheet List page.
"""
import logging
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import COLORS, card_style
from src.ui.design import bind_style, current as _t, label
logger = logging.getLogger(__name__)

_COLORS = COLORS

def _TABLE_STYLE() -> str:
    return f"""
    QTableWidget {{
        border: none;
        background: {_t().surface};
        gridline-color: {_COLORS['border']};
        font-size: 13px;
        color: {_COLORS['text_dark']};
    }}
    QTableWidget::item {{
        padding: 8px 12px;
    }}
    QTableWidget::item:selected {{
        background-color: {_t().accent_soft};
        color: {_COLORS['text_dark']};
    }}
    QHeaderView::section {{
        background-color: {_t().surface_alt};
        color: {_COLORS['text_muted']};
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 0.5px;
        padding: 8px 12px;
        border: none;
        border-bottom: 2px solid {_COLORS['border']};
    }}
"""

def _INPUT_STYLE() -> str:
    return f"""
    QLineEdit, QComboBox {{
        padding: 8px 12px;
        border: 1px solid {_COLORS['border']};
        border-radius: 6px;
        font-size: 13px;
        color: {_COLORS['text_dark']};
        background: {_t().surface};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {_COLORS['primary']};
    }}
"""

def _BTN_STYLE() -> str:
    return f"""
    QPushButton {{
        background-color: {_COLORS['primary']};
        color: {_t().text_on_accent};
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

def _NAV_BTN_STYLE() -> str:
    return f"""
    QPushButton {{
        background-color: {_t().surface};
        color: {_COLORS['primary']};
        padding: 6px 14px;
        border: 1px solid {_COLORS['primary']};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {_t().accent_soft};
    }}
    QPushButton:disabled {{
        color: {_COLORS['disabled']};
        border-color: {_COLORS['disabled']};
        background-color: {_t().surface};
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
        self._timesheets: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(16)
        bind_style(self, lambda: f"TimesheetListView {{ background-color: {_COLORS['bg']}; }}")

        header_row = QHBoxLayout()

        header_lbl = label("Timesheets", "title")
        header_row.addWidget(header_lbl)
        header_row.addStretch()

        self.refresh_btn = QPushButton("↻  Refresh")
        bind_style(self.refresh_btn, _BTN_STYLE)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_row.addWidget(self.refresh_btn)

        main_layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search name, status, date, or hours...")
        self.search_input.setClearButtonEnabled(True)
        bind_style(self.search_input, _INPUT_STYLE)
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self.search_input, stretch=2)

        self.status_filter = QComboBox()
        bind_style(self.status_filter, _INPUT_STYLE)
        self.status_filter.setFixedHeight(38)
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(self.status_filter, stretch=1)

        main_layout.addLayout(filter_row)

        self.summary_lbl = QLabel("Page total: 0 h")
        bind_style(self.summary_lbl, lambda: f"font-size: 12px; font-weight: 600; color: {_COLORS['text_dark']};")
        main_layout.addWidget(self.summary_lbl)

        card = QFrame()
        card.setObjectName("card")
        bind_style(card, lambda: card_style("card"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Workflow State", "Status", "Start Date", "End Date", "Total Hours"]
        )
        bind_style(self.table, _TABLE_STYLE)
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
        bind_style(self.loading_lbl, lambda: f"color: {_COLORS['text_muted']}; font-size: 14px; padding: 30px;")
        self.loading_lbl.hide()
        card_layout.addWidget(self.loading_lbl)

        self.empty_lbl = QLabel("No timesheets found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.empty_lbl, lambda: f"color: {_COLORS['text_muted']}; font-size: 13px; padding: 40px;")
        self.empty_lbl.hide()
        card_layout.addWidget(self.empty_lbl)

        main_layout.addWidget(card, stretch=1)

        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(10)

        self.prev_btn = QPushButton("← Prev")
        bind_style(self.prev_btn, _NAV_BTN_STYLE)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev_clicked)
        pagination_row.addWidget(self.prev_btn)

        self.page_lbl = QLabel("Page 1")
        bind_style(self.page_lbl, lambda: f"font-size: 12px; color: {_COLORS['text_muted']};")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        pagination_row.addWidget(self.page_lbl)

        self.next_btn = QPushButton("Next →")
        bind_style(self.next_btn, _NAV_BTN_STYLE)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_clicked)
        pagination_row.addWidget(self.next_btn)

        pagination_row.addStretch()

        self.result_count_lbl = QLabel("")
        bind_style(self.result_count_lbl, lambda: f"font-size: 12px; color: {_COLORS['text_muted']};")
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
        self._timesheets = list(timesheets)
        self._sync_status_filter_options()
        self.loading_lbl.hide()
        self._apply_filters()

    def _sync_status_filter_options(self) -> None:
        current = self.status_filter.currentText()
        statuses = sorted(
            {
                str(timesheet.get("status") or "").strip()
                for timesheet in self._timesheets
                if str(timesheet.get("status") or "").strip()
            }
        )
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem("All statuses")
        self.status_filter.addItems(statuses)
        if current and current in ["All statuses", *statuses]:
            self.status_filter.setCurrentText(current)
        self.status_filter.blockSignals(False)

    def _apply_filters(self) -> None:
        query = self.search_input.text().strip().lower()
        status = self.status_filter.currentText()
        filtered = [
            timesheet for timesheet in self._timesheets
            if self._matches_filters(timesheet, query, status)
        ]
        self._render_timesheets(filtered)
        self._update_summary(filtered)

    def _matches_filters(
        self,
        timesheet: Dict[str, Any],
        query: str,
        status: str,
    ) -> bool:
        if status and status != "All statuses" and str(timesheet.get("status", "")) != status:
            return False
        if not query:
            return True
        searchable = " ".join(
            str(timesheet.get(key, ""))
            for key in (
                "name",
                "workflow_state",
                "status",
                "start_date",
                "end_date",
                "total_hours",
            )
        ).lower()
        return query in searchable

    def _render_timesheets(self, timesheets: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        self._row_timesheet_names = []

        if not timesheets:
            self.empty_lbl.setText(
                "No matching timesheets found." if self._timesheets else "No timesheets found."
            )
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

    def _update_summary(self, timesheets: List[Dict[str, Any]]) -> None:
        total_hours = 0.0
        status_counts: Dict[str, int] = {}
        for timesheet in timesheets:
            try:
                total_hours += float(timesheet.get("total_hours") or 0)
            except (TypeError, ValueError):
                pass
            status = str(timesheet.get("status") or "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        status_text = ", ".join(
            f"{count} {status}" for status, count in sorted(status_counts.items())
        )
        summary = f"Page total: {total_hours:g} h"
        if timesheets:
            summary = f"{summary} across {len(timesheets)} visible"
        if status_text:
            summary = f"{summary} | {status_text}"
        self.summary_lbl.setText(summary)

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        """Shows/hides the loading indicator and disables interactive controls."""
        self.refresh_btn.setEnabled(not is_loading)
        self.prev_btn.setEnabled(not is_loading)
        self.next_btn.setEnabled(not is_loading)
        self.table.setEnabled(not is_loading)
        self.search_input.setEnabled(not is_loading)
        self.status_filter.setEnabled(not is_loading)

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
