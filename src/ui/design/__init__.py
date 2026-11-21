"""Work Tracker design system. See docs/design-system.md."""

from src.ui.design.manager import bind_style, current, manager
from src.ui.design.qss import build_stylesheet
from src.ui.design.tokens import DARK, FONT, LIGHT, RADIUS, SPACE, THEMES, Theme
from src.ui.design.widgets import Card, PageHeader, StatCard, button, label, set_prop


def apply_theme(app=None) -> None:
    """Install the saved theme's stylesheet. Call once after QApplication()."""
    manager.apply()


__all__ = [
    "apply_theme", "build_stylesheet", "bind_style", "current", "manager",
    "Theme", "LIGHT", "DARK", "THEMES", "SPACE", "RADIUS", "FONT",
    "Card", "StatCard", "PageHeader", "button", "label", "set_prop",
]
