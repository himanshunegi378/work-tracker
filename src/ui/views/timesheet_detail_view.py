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

from src.ui.theme import COLORS, card_style
from src.ui.design import bind_style, button, current as _t, label as design_label
_COLORS = COLORS

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

def _TABLE_STYLE() -> str:
    return f"""
    QTableWidget {{
        border: none;
        background: {_t().surface};
        gridline-color: {_COLORS['border']};
        font-size: 13px;
        color: {_COLORS['text_dark']};
    }}
    QTableWidget::item:selected {{
        background-color: {_t().accent_soft};
        color: {_t().text};
    }}
    QHeaderView::section {{
        background-color: {_t().surface_alt};
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
    edit_entry_requested = Signal(str)     # row name
    delete_entry_requested = Signal(str)   # row name
    submit_requested = Signal()
    delete_timesheet_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._summary_labels: Dict[str, QLabel] = {}
        self._entries: Dict[str, dict] = {}
        self._editable = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 20)
        main_layout.setSpacing(16)
        bind_style(self, lambda: f"TimesheetDetailView {{ background-color: {_COLORS['bg']}; }}")

        header_row = QHBoxLayout()
        self.back_btn = QPushButton("← Back")
        bind_style(self.back_btn, _BTN_STYLE)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_btn)

        self.title_lbl = QLabel("Timesheet Detail")
        bind_style(self.title_lbl, lambda: f"font-size: 22px; font-weight: bold; color: {_COLORS['text_dark']};")
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()
        main_layout.addLayout(header_row)

        summary_card = QFrame()
        summary_card.setObjectName("summary_card")
        bind_style(summary_card, lambda: card_style("summary_card"))
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
            bind_style(label, lambda: f"font-size: 12px; color: {_COLORS['text_muted']};")
            value = QLabel("—")
            bind_style(value, lambda: f"font-size: 13px; color: {_COLORS['text_dark']};")
            value.setWordWrap(True)
            summary_layout.addWidget(label, row, col)
            summary_layout.addWidget(value, row, col + 1)
            self._summary_labels[key] = value

        main_layout.addWidget(summary_card)

        logs_card = QFrame()
        logs_card.setObjectName("logs_card")
        bind_style(logs_card, lambda: card_style("logs_card"))
        logs_layout = QVBoxLayout(logs_card)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(0)

        self.time_logs_table = QTableWidget(0, 7)
        self.time_logs_table.setHorizontalHeaderLabels(
            ["Activity", "Project", "From", "To", "Hours", "Billable", "Description"]
        )
        bind_style(self.time_logs_table, _TABLE_STYLE)
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
        bind_style(self.loading_lbl, lambda: f"color: {_COLORS['text_muted']}; font-size: 14px; padding: 30px;")
        self.loading_lbl.hide()
        logs_layout.addWidget(self.loading_lbl)

        self.empty_lbl = QLabel("No time logs found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.empty_lbl, lambda: f"color: {_COLORS['text_muted']}; font-size: 13px; padding: 40px;")
        self.empty_lbl.hide()
        logs_layout.addWidget(self.empty_lbl)

        main_layout.addWidget(logs_card, stretch=1)

        # Actions (enabled only for Pending drafts; same rules as the CLI)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.edit_btn = button("Edit entry", "secondary")
        self.delete_entry_btn = button("Delete entry", "secondary")
        self.delete_timesheet_btn = button("Delete timesheet", "danger")
        self.submit_btn = button("Submit timesheet", "primary")
        self.actions_note = design_label("", "caption")
        for widget in (self.edit_btn, self.delete_entry_btn):
            actions.addWidget(widget)
        actions.addWidget(self.actions_note)
        actions.addStretch()
        actions.addWidget(self.delete_timesheet_btn)
        actions.addWidget(self.submit_btn)
        main_layout.addLayout(actions)

        self.edit_btn.clicked.connect(lambda: self._emit_for_selected(self.edit_entry_requested))
        self.delete_entry_btn.clicked.connect(lambda: self._emit_for_selected(self.delete_entry_requested))
        self.submit_btn.clicked.connect(self.submit_requested.emit)
        self.delete_timesheet_btn.clicked.connect(self.delete_timesheet_requested.emit)
        self.time_logs_table.itemSelectionChanged.connect(self._update_actions)
        self.time_logs_table.itemDoubleClicked.connect(lambda _item: self._emit_for_selected(self.edit_entry_requested))
        self._update_actions()

    # -- actions ---------------------------------------------------------
    def selected_entry_name(self) -> str:
        item = self.time_logs_table.item(self.time_logs_table.currentRow(), 0) if self.time_logs_table.currentRow() >= 0 else None
        return str(item.data(Qt.UserRole)) if item is not None and item.data(Qt.UserRole) else ""

    def entry(self, row_name: str) -> dict:
        return self._entries.get(row_name, {})

    @property
    def is_editable(self) -> bool:
        return self._editable

    def _emit_for_selected(self, signal) -> None:
        name = self.selected_entry_name()
        if name:
            signal.emit(name)

    def _update_actions(self) -> None:
        has_selection = bool(self.selected_entry_name())
        self.edit_btn.setEnabled(self._editable and has_selection)
        self.delete_entry_btn.setEnabled(self._editable and has_selection)
        self.submit_btn.setEnabled(self._editable and bool(self._entries))
        self.delete_timesheet_btn.setEnabled(self._editable)
        self.actions_note.setText("" if self._editable else "Only Pending timesheets can be changed.")

    def confirm(self, title: str, text: str) -> bool:
        """Ask a yes/no question (overridable in tests)."""
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, self)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    @Slot(dict)
    def display_timesheet_detail(self, detail: dict) -> None:
        """Render one normalized timesheet detail payload."""
        self._editable = detail.get("workflow_state") in ("Pending", "", None)
        self._entries = {str(log.get("name")): log for log in detail.get("time_logs") or [] if log.get("name")}
        self.title_lbl.setText(f"Timesheet Detail • {detail.get('name') or '—'}")
        for key, label in self._summary_labels.items():
            value = detail.get(key)
            label.setText("—" if value in (None, "") else str(value))

        self.time_logs_table.setRowCount(0)
        time_logs: List[dict] = detail.get("time_logs") or []
        if not time_logs:
            self.empty_lbl.show()
            self.time_logs_table.hide()
            self._update_actions()
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
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, str(log.get("name") or ""))
                self.time_logs_table.setItem(row, column, item)
        self._update_actions()

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        """Shows/hides the loading indicator and disables interactive controls."""
        self.back_btn.setEnabled(not is_loading)
        if is_loading:
            for widget in (self.edit_btn, self.delete_entry_btn, self.submit_btn, self.delete_timesheet_btn):
                widget.setEnabled(False)
        if is_loading:
            self.time_logs_table.hide()
            self.empty_lbl.hide()
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()
            self._update_actions()

    def show_error_titled(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    @Slot(str)
    def show_error(self, message: str) -> None:
        """Displays a modal error dialog to the user."""
        QMessageBox.critical(self, "Error Fetching Timesheet Detail", message)
