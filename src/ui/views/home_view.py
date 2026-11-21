"""
home_view.py  (migrated)
------------------------
Pure View component for the Projects list page.

Changes vs. previous version:
  - Removed "+ New Project" button and Signal (no POST endpoint in ProjectService)
  - Removed AddProjectDialog inner class
  - Added: search input (debounced), Refresh button, loading indicator, pagination
  - display_projects() now accepts List[Dict[str, Any]] from the API
  - All new interactive widgets communicate via Signals to the Presenter
"""
import logging
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import COLORS, card_style
from src.ui.views.project_card_view import ProjectCard
from src.ui.design import bind_style, current as _t, label

logger = logging.getLogger(__name__)

# ── Shared style tokens ───────────────────────────────────────────────────────
_C = COLORS

def _INPUT_STYLE() -> str:
    return f"""
    QLineEdit {{
        padding: 8px 12px;
        border: 1px solid {_C['border']};
        border-radius: 6px;
        font-size: 13px;
        color: {_C['text_dark']};
        background: {_t().surface};
    }}
    QLineEdit:focus {{ border: 1px solid {_C['primary']}; }}
"""

def _BTN_STYLE() -> str:
    return f"""
    QPushButton {{
        background-color: {_C['primary']};
        color: {_t().text_on_accent};
        padding: 8px 18px;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {_C['primary_hov']}; }}
    QPushButton:disabled {{ background-color: {_C['disabled']}; }}
"""

def _NAV_BTN() -> str:
    return f"""
    QPushButton {{
        background-color: {_t().surface};
        color: {_C['primary']};
        padding: 6px 14px;
        border: 1px solid {_C['primary']};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {_t().accent_soft}; }}
    QPushButton:disabled {{ color: {_C['disabled']}; border-color: {_C['disabled']}; background: {_t().surface}; }}
"""


class HomeView(QWidget):
    """
    Project list page — read-only view driven by the Frappe ProjectService.

    Signals:
        fetch_requested(search_text: str, page: int)
    """
    fetch_requested = Signal(str, int)   # (search_text, page_index)
    _DEBOUNCE_MS = 300

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._current_page: int = 0
        self._page_size: int = 20
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_fired)
        self._setup_ui()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(30, 30, 30, 20)
        main.setSpacing(16)
        bind_style(self, lambda: f"background-color: {_C['bg']};")

        # Header row
        header_row = QHBoxLayout()
        title = label("Projects", "title")
        header_row.addWidget(title)
        header_row.addStretch()

        self.refresh_btn = QPushButton("↻  Refresh")
        bind_style(self.refresh_btn, _BTN_STYLE)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh)
        header_row.addWidget(self.refresh_btn)
        main.addLayout(header_row)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search projects…")
        bind_style(self.search_input, _INPUT_STYLE)
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self._on_search_changed)
        main.addWidget(self.search_input)

        # Card frame with scroll area
        card = QFrame()
        card.setObjectName("card")
        bind_style(card, lambda: card_style("card"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_container)
        card_layout.addWidget(self.scroll)

        # Loading label (hidden by default)
        self.loading_lbl = QLabel("  Loading…")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.loading_lbl, lambda: f"color: {_C['text_muted']}; font-size: 14px; padding: 30px;")
        self.loading_lbl.hide()
        card_layout.addWidget(self.loading_lbl)

        # Empty state label
        self.empty_lbl = QLabel("No projects found.")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        bind_style(self.empty_lbl, lambda: f"color: {_C['text_muted']}; font-size: 13px; padding: 40px;")
        self.empty_lbl.hide()
        card_layout.addWidget(self.empty_lbl)

        main.addWidget(card, stretch=1)

        # Pagination bar
        pag = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev")
        bind_style(self.prev_btn, _NAV_BTN)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev)

        self.page_lbl = QLabel("Page 1")
        bind_style(self.page_lbl, lambda: f"font-size: 12px; color: {_C['text_muted']};")
        self.page_lbl.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton("Next →")
        bind_style(self.next_btn, _NAV_BTN)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next)

        self.count_lbl = QLabel("")
        bind_style(self.count_lbl, lambda: f"font-size: 12px; color: {_C['text_muted']};")

        pag.addWidget(self.prev_btn)
        pag.addWidget(self.page_lbl)
        pag.addWidget(self.next_btn)
        pag.addStretch()
        pag.addWidget(self.count_lbl)
        main.addLayout(pag)

    # ── Private event handlers ─────────────────────────────────────────────────

    def _on_search_changed(self, _: str) -> None:
        self._debounce_timer.start(self._DEBOUNCE_MS)

    def _on_debounce_fired(self) -> None:
        self._current_page = 0
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    def _on_refresh(self) -> None:
        self._current_page = 0
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    def _on_prev(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    def _on_next(self) -> None:
        self._current_page += 1
        self.fetch_requested.emit(self.search_input.text().strip(), self._current_page)

    # ── Public interface (called by Presenter) ─────────────────────────────────

    @Slot(list)
    def display_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Renders the list of project cards."""
        # Clear existing cards
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.loading_lbl.hide()

        if not projects:
            self.scroll.hide()
            self.empty_lbl.show()
            return

        self.empty_lbl.hide()
        self.scroll.show()
        for p in projects:
            self.list_layout.addWidget(ProjectCard(p))

    @Slot(bool)
    def set_loading(self, is_loading: bool) -> None:
        self.search_input.setEnabled(not is_loading)
        self.refresh_btn.setEnabled(not is_loading)
        self.prev_btn.setEnabled(not is_loading and self._current_page > 0)
        self.next_btn.setEnabled(not is_loading)
        if is_loading:
            self.scroll.hide()
            self.empty_lbl.hide()
            self.loading_lbl.show()
        else:
            self.loading_lbl.hide()

    @Slot(int, int, int)
    def set_page_info(self, current_page: int, page_size: int, result_count: int) -> None:
        self._current_page = current_page
        self._page_size = page_size
        self.page_lbl.setText(f"Page {current_page + 1}")
        self.prev_btn.setEnabled(current_page > 0)
        self.next_btn.setEnabled(result_count >= page_size)
        start = current_page * page_size + 1
        end = current_page * page_size + result_count
        self.count_lbl.setText(
            f"Showing {start}–{end} results" if result_count > 0 else "No results"
        )

    @Slot(str)
    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error Loading Projects", message)
