"""Leave page: your leave applications in a table, with a status filter and paging."""

from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.ui.design import bind_style, label
from src.ui.theme import COLORS, card_style
from src.ui.views.employee_filter import EmployeeFilter
from src.ui.views.activity_list_view import _BTN_STYLE, _NAV_BTN_STYLE, _TABLE_STYLE

ALL_TYPES = "All types"
STATUSES = ["All", "Open", "Approved", "Rejected", "Cancelled"]
_HEADERS = ["#", "Employee", "Type", "From", "To", "Days", "Status", "ID"]


def _days_text(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return str(int(number)) if number == int(number) else str(number)


class LeaveListView(QWidget):
    """Pure view. Emits `fetch_requested(status, page)`; the presenter feeds it rows."""

    fetch_requested = Signal(str, str, str, int)  # (status, type, employee, page); "" = all / me, "*" = everyone

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._page = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 20)
        root.setSpacing(16)
        bind_style(self, lambda: f"LeaveListView {{ background-color: {COLORS['bg']}; }}")

        header = QHBoxLayout()
        header.addWidget(label("Leave", "title"))
        header.addStretch()
        self.employee_combo = EmployeeFilter()
        self.employee_combo.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self.employee_combo)
        self.type_combo = QComboBox()
        self.type_combo.addItem(ALL_TYPES)
        self.type_combo.setMinimumWidth(150)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self.type_combo)
        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self.status_combo)
        self.refresh_btn = QPushButton("↻  Refresh")
        bind_style(self.refresh_btn, _BTN_STYLE)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._emit)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        self.balance_row = QHBoxLayout()
        self.balance_row.setSpacing(12)
        root.addLayout(self.balance_row)

        card = QFrame()
        card.setObjectName("card")
        bind_style(card, lambda: card_style("card"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        bind_style(self.table, _TABLE_STYLE)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.table)

        self.loading_lbl = QLabel("Loading…")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.loading_lbl, lambda: f"color: {COLORS['text_muted']}; font-size: 14px; padding: 30px;")
        self.loading_lbl.hide()
        card_layout.addWidget(self.loading_lbl)

        self.empty_lbl = QLabel("No leave applications found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.empty_lbl, lambda: f"color: {COLORS['text_muted']}; font-size: 13px; padding: 40px;")
        self.empty_lbl.hide()
        card_layout.addWidget(self.empty_lbl)
        root.addWidget(card, stretch=1)

        pager = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev")
        self.next_btn = QPushButton("Next →")
        for btn, slot in ((self.prev_btn, self._on_prev), (self.next_btn, self._on_next)):
            bind_style(btn, _NAV_BTN_STYLE)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setEnabled(False)
            btn.clicked.connect(slot)
        self.page_lbl = QLabel("Page 1")
        bind_style(self.page_lbl, lambda: f"font-size: 12px; color: {COLORS['text_muted']};")
        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_lbl)
        pager.addWidget(self.next_btn)
        pager.addStretch()
        root.addLayout(pager)

    def display_balances(self, balances: List[Dict[str, Any]]) -> None:
        """Show one card per leave type: days remaining, with taken/allocated underneath."""
        while self.balance_row.count():
            item = self.balance_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for balance in balances:
            card = QFrame()
            card.setObjectName("balanceCard")
            bind_style(card, lambda: card_style("balanceCard"))
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(2)
            layout.addWidget(label(balance["leave_type"], "caption"))
            layout.addWidget(label(f"{_days_text(balance.get('remaining_leaves'))} left", "title"))
            detail = (
                f"{_days_text(balance.get('leaves_taken'))} taken of "
                f"{_days_text(balance.get('total_leaves'))}"
            )
            pending = balance.get("leaves_pending_approval") or 0
            if pending:
                detail += f" · {_days_text(pending)} pending"
            layout.addWidget(label(detail, "caption"))
            self.balance_row.addWidget(card)
        self.balance_row.addStretch()

    def selected_status(self) -> str:
        text = self.status_combo.currentText()
        return "" if text == "All" else text

    def selected_type(self) -> str:
        text = self.type_combo.currentText()
        return "" if text == ALL_TYPES else text

    def selected_employee(self) -> str:
        return self.employee_combo.selected_employee()

    def set_employees(self, people: List[Dict[str, str]]) -> None:
        self.employee_combo.set_people(people)

    def set_leave_types(self, types: List[str]) -> None:
        """Fill the type dropdown, keeping the current choice if it still exists."""
        current = self.selected_type()
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem(ALL_TYPES)
        self.type_combo.addItems(types)
        index = self.type_combo.findText(current) if current else 0
        self.type_combo.setCurrentIndex(max(index, 0))
        self.type_combo.blockSignals(False)

    def _emit(self) -> None:
        self.fetch_requested.emit(
            self.selected_status(), self.selected_type(), self.selected_employee(), self._page
        )

    def _on_filter_changed(self, _index: int) -> None:
        self._page = 0
        self._emit()

    def _on_prev(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._emit()

    def _on_next(self) -> None:
        self._page += 1
        self._emit()

    @Slot(list)
    def display_leaves(self, leaves: List[Dict[str, Any]], first_number: int = 1) -> None:
        self.table.setRowCount(0)
        self.loading_lbl.hide()
        if not leaves:
            self.empty_lbl.show()
            self.table.hide()
            return
        self.empty_lbl.hide()
        self.table.show()
        for offset, leave in enumerate(leaves):
            values = [
                str(first_number + offset), leave.get("employee_name"), leave.get("leave_type"), leave.get("from_date"), leave.get("to_date"),
                _days_text(leave.get("total_leave_days")), leave.get("status"), leave.get("name"),
            ]
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value) if value not in (None, "") else "—")
                if col in (0, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        self.status_combo.setEnabled(not is_loading)
        self.type_combo.setEnabled(not is_loading)
        self.employee_combo.setEnabled(not is_loading)
        self.refresh_btn.setEnabled(not is_loading)
        if is_loading:
            self.table.hide()
            self.empty_lbl.hide()
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()

    def set_page_info(self, page: int, page_size: int, result_count: int) -> None:
        self._page = page
        self.page_lbl.setText(f"Page {page + 1}")
        self.prev_btn.setEnabled(page > 0)
        self.next_btn.setEnabled(result_count >= page_size)

    @Slot(str)
    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error Fetching Leave", message)
