"""
activity_list_view.py
---------------------
Pure View component for the Activity List page.

Responsibilities (View layer only):
  - Render search bar, refresh button, QTableWidget, loading indicator, pagination bar
  - Emit signals when the user takes actions
  - Expose slots to display data, show errors, toggle loading state

No business logic, no service / network calls here.
"""
import logging
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ── Style constants ───────────────────────────────────────────────────────────
_COLORS = {
    "bg": "#F5F7FA",
    "card": "#FFFFFF",
    "border": "#E0E0E0",
    "primary": "#2196F3",
    "primary_hover": "#1976D2",
    "text_dark": "#263238",
    "text_muted": "#78909C",
    "success": "#4CAF50",
    "danger": "#F44336",
    "disabled": "#B0BEC5",
}

_INPUT_STYLE = f"""
    QLineEdit {{
        padding: 8px 12px;
        border: 1px solid {_COLORS['border']};
        border-radius: 6px;
        font-size: 13px;
        color: {_COLORS['text_dark']};
        background: white;
    }}
    QLineEdit:focus {{
        border: 1px solid {_COLORS['primary']};
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


class ActivityListView(QWidget):
    """
    UI component for browsing Activity Types fetched from the backend.

    Signals:
        fetch_requested(search_text: str, page: int):
            Emitted whenever the user changes search text or navigates pages.
    """

    fetch_requested = Signal(str, int)  # (search_text, page_index)

    # How many milliseconds to debounce the search input before emitting
    _DEBOUNCE_MS = 300

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._current_page: int = 0
        self._total_results: int = 0
        self._page_size: int = 20  # mirrors presenter default; used for UI only
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)
        self._setup_ui()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(16)
        self.setStyleSheet(f"background-color: {_COLORS['bg']};")

        # 1 ── Header row ──────────────────────────────────────────────────────
        header_row = QHBoxLayout()

        header_lbl = QLabel("⚡ Activity Types")
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

        # 2 ── Search bar ──────────────────────────────────────────────────────
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search activity types…")
        self.search_input.setStyleSheet(_INPUT_STYLE)
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.search_input)

        # 3 ── Card frame containing table ────────────────────────────────────
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

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["#", "Activity Name"])
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.table)

        # Loading overlay label (hidden by default)
        self.loading_lbl = QLabel("  Loading…")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        self.loading_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 14px; padding: 30px;"
        )
        self.loading_lbl.hide()
        card_layout.addWidget(self.loading_lbl)

        # Empty state label (hidden until data arrives)
        self.empty_lbl = QLabel("No activity types found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet(
            f"color: {_COLORS['text_muted']}; font-size: 13px; padding: 40px;"
        )
        self.empty_lbl.hide()
        card_layout.addWidget(self.empty_lbl)

        main_layout.addWidget(card, stretch=1)

        # 4 ── Pagination bar ──────────────────────────────────────────────────
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

    # ── Private event handlers ─────────────────────────────────────────────────

    def _on_search_changed(self, text: str) -> None:
        """Restarts the debounce timer whenever the search text changes."""
        self._debounce_timer.start(self._DEBOUNCE_MS)

    def _on_debounce_timeout(self) -> None:
        """Fired after the debounce window elapses — resets to page 0 and fetches."""
        self._current_page = 0
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    def _on_refresh_clicked(self) -> None:
        self._current_page = 0
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    def _on_prev_clicked(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.fetch_requested.emit(
                self.search_input.text().strip(), self._current_page
            )

    def _on_next_clicked(self) -> None:
        self._current_page += 1
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    # ── Public interface (called by Presenter) ─────────────────────────────────

    @Slot(list)
    def display_activities(self, activities: List[Dict[str, Any]]) -> None:
        """Populates the table with the fetched activity list."""
        self.table.setRowCount(0)
        self.loading_lbl.hide()

        if not activities:
            self.empty_lbl.show()
            self.table.hide()
            return

        self.empty_lbl.hide()
        self.table.show()

        for idx, activity in enumerate(activities):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Column 0 — sequential number
            num_item = QTableWidgetItem(
                str(self._current_page * self._page_size + idx + 1)
            )
            num_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, num_item)

            # Column 1 — activity name
            name = activity.get("name") or activity.get("raw_data", "—")
            self.table.setItem(row, 1, QTableWidgetItem(str(name)))

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        """Shows/hides the loading indicator and disables interactive controls."""
        self.search_input.setEnabled(not is_loading)
        self.refresh_btn.setEnabled(not is_loading)
        self.prev_btn.setEnabled(not is_loading)
        self.next_btn.setEnabled(not is_loading)

        if is_loading:
            self.table.hide()
            self.empty_lbl.hide()
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()

    @Slot(int, int, int)
    def set_page_info(self, current_page: int, page_size: int, result_count: int) -> None:
        """
        Updates the pagination controls.

        Args:
            current_page: 0-based page index.
            page_size:    Records per page.
            result_count: Number of records returned in the current page.
        """
        self._current_page = current_page
        self._page_size = page_size

        self.page_lbl.setText(f"Page {current_page + 1}")
        self.prev_btn.setEnabled(current_page > 0)
        # We can go Next if we received a full page (there may be more)
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
        QMessageBox.critical(self, "Error Fetching Activities", message)
