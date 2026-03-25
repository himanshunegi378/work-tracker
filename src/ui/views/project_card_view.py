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

# ── Status badge colour mapping ───────────────────────────────────────────────
_STATUS_COLORS: Dict[str, str] = {
    "open":      "#4CAF50",
    "completed": "#2196F3",
    "cancelled": "#9E9E9E",
}

_PRIORITY_COLORS: Dict[str, str] = {
    "high":   "#F44336",
    "medium": "#FF9800",
    "low":    "#78909C",
}


def _badge(text: str, color: str) -> QLabel:
    """Helper: create a small coloured pill label."""
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"""
        color: white;
        background-color: {color};
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 9px;
        font-weight: bold;
        """
    )
    return lbl


class ProjectCard(QFrame):
    """A styled card representing a single Frappe project."""

    def __init__(self, project: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            ProjectCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
            ProjectCard:hover {
                border: 1px solid #2196F3;
                background-color: #f5faff;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Row 1: Name + Status badge + Priority badge ───────────────────────
        header = QHBoxLayout()

        name_lbl = QLabel(self.project.get("name") or "—")
        name_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #263238;")
        header.addWidget(name_lbl)
        header.addStretch()

        status_raw  = (self.project.get("status") or "open").lower()
        priority_raw = (self.project.get("priority") or "medium").lower()

        status_color   = _STATUS_COLORS.get(status_raw,   "#9E9E9E")
        priority_color = _PRIORITY_COLORS.get(priority_raw, "#78909C")

        header.addWidget(_badge(status_raw,   status_color))
        header.addWidget(_badge(priority_raw, priority_color))
        layout.addLayout(header)

        # ── Row 2: Project ID ─────────────────────────────────────────────────
        pid = self.project.get("id") or ""
        if pid:
            id_lbl = QLabel(f"ID: {pid}")
            id_lbl.setStyleSheet("font-size: 11px; color: #90A4AE;")
            layout.addWidget(id_lbl)

        # ── Row 3: Description ────────────────────────────────────────────────
        desc = self.project.get("description") or ""
        if desc:
            desc_lbl = QLabel(str(desc))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #546E7A; font-size: 12px;")
            layout.addWidget(desc_lbl)

        # ── Row 4: Active indicator ───────────────────────────────────────────
        is_active = self.project.get("is_active", True)
        if not is_active:
            inactive_lbl = QLabel("⚠ Inactive")
            inactive_lbl.setStyleSheet("font-size: 11px; color: #FF9800;")
            layout.addWidget(inactive_lbl)
