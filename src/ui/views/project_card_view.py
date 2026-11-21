"""
project_card_view.py  (migrated)
---------------------------------
Renders a single project record fetched from the Frappe API.

Accepts a plain Dict[str, Any] instead of the former local Project dataclass,
eliminating the coupling to persistence-layer models.

Expected dict shape (from ProjectService.get_projects):
    {
        "id":          str,   # "PROJ-0006"
        "name":        str,   # "Crowst"
        "description": str | None,
        "status":      str,   # "Open" | "Completed" | "Cancelled"
        "priority":    str,   # "Medium" | "High" | "Low"
        "is_active":   bool
    }
"""
from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from src.ui.design import bind_style, current as _t

# ── Status badge colour mapping (theme role names) ───────────────────────────────────────────────
_STATUS_COLORS: Dict[str, str] = {
    "open":      "success",
    "completed": "accent",
    "cancelled": "text_muted",
}

_PRIORITY_COLORS: Dict[str, str] = {
    "high":   "danger",
    "medium": "warning",
    "low":    "text_muted",
}


def _badge(text: str, color_role: str) -> QLabel:
    """Helper: create a small coloured pill label."""
    lbl = QLabel(text.upper())
    bind_style(lbl, lambda: f"""
        color: {_t().text_on_accent};
        background-color: {getattr(_t(), color_role)};
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 9px;
        font-weight: bold;
        """)
    return lbl


class ProjectCard(QFrame):
    """A styled card representing a single Frappe project."""

    def __init__(self, project: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        bind_style(self, lambda: f"""
            ProjectCard {{
                background-color: {_t().surface};
                border: 1px solid {_t().border};
                border-radius: 8px;
                padding: 12px;
            }}
            ProjectCard:hover {{
                border: 1px solid {_t().accent};
                background-color: {_t().accent_soft};
            }}
            """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Row 1: Name + Status badge + Priority badge ───────────────────────
        header = QHBoxLayout()

        name_lbl = QLabel(self.project.get("name") or "—")
        bind_style(name_lbl, lambda: f"font-weight: bold; font-size: 14px; color: {_t().text};")
        header.addWidget(name_lbl)
        header.addStretch()

        status_raw  = (self.project.get("status") or "open").lower()
        priority_raw = (self.project.get("priority") or "medium").lower()

        status_color   = _STATUS_COLORS.get(status_raw,   "text_muted")
        priority_color = _PRIORITY_COLORS.get(priority_raw, "text_muted")

        header.addWidget(_badge(status_raw,   status_color))
        header.addWidget(_badge(priority_raw, priority_color))
        layout.addLayout(header)

        # ── Row 2: Project ID ─────────────────────────────────────────────────
        pid = self.project.get("id") or ""
        if pid:
            id_lbl = QLabel(f"ID: {pid}")
            bind_style(id_lbl, lambda: f"font-size: 11px; color: {_t().text_muted};")
            layout.addWidget(id_lbl)

        # ── Row 3: Description ────────────────────────────────────────────────
        desc = self.project.get("description") or ""
        if desc:
            desc_lbl = QLabel(str(desc))
            desc_lbl.setWordWrap(True)
            bind_style(desc_lbl, lambda: f"color: {_t().text_secondary}; font-size: 12px;")
            layout.addWidget(desc_lbl)

        # ── Row 4: Active indicator ───────────────────────────────────────────
        is_active = self.project.get("is_active", True)
        if not is_active:
            inactive_lbl = QLabel("⚠ Inactive")
            bind_style(inactive_lbl, lambda: f"font-size: 11px; color: {_t().warning};")
            layout.addWidget(inactive_lbl)
