"""Reusable, token-driven building blocks. Prefer these over ad-hoc QFrame/QLabel styling."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui.design.tokens import SPACE


def set_prop(widget: QWidget, name: str, value) -> None:
    """Set a dynamic property and re-polish so the stylesheet re-evaluates."""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def label(text: str, role: str = "body", tone: Optional[str] = None, parent=None) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setProperty("role", role)
    if tone:
        lbl.setProperty("tone", tone)
    return lbl


def button(text: str, variant: str = "primary", parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class Card(QFrame):
    """White rounded surface. Add children to `.body` (a QVBoxLayout)."""

    def __init__(self, parent=None, padding: int = SPACE["xl"]):
        super().__init__(parent)
        self.setProperty("card", "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding - SPACE["xs"], padding, padding - SPACE["xs"])
        self.body.setSpacing(SPACE["sm"])


class StatCard(Card):
    """Overline label + large metric value."""

    def __init__(self, title: str, value: str = "0", tone: str = "accent", parent=None):
        super().__init__(parent, padding=SPACE["xl"] - SPACE["xs"])
        self.body.setSpacing(SPACE["xs"])
        self.title_lbl = label(title.upper(), "overline")
        self.value_lbl = label(value, "metric", tone)
        self.body.addWidget(self.title_lbl)
        self.body.addWidget(self.value_lbl)

    def set_value(self, value) -> None:
        self.value_lbl.setText(str(value))


class PageHeader(QWidget):
    """Page title with optional subtitle and a right-aligned actions area."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        text = QVBoxLayout()
        text.setSpacing(SPACE["xxs"])
        text.addWidget(label(title, "title"))
        if subtitle:
            text.addWidget(label(subtitle, "caption"))
        row.addLayout(text)
        row.addStretch()
        self.actions = QHBoxLayout()
        self.actions.setSpacing(SPACE["sm"])
        row.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)
