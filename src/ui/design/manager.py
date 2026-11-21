"""Runtime theme state: current theme, persistence, live switching, rebindable styles."""

import logging
import weakref
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.ui.design.qss import build_stylesheet
from src.ui.design.tokens import DARK, LIGHT, THEMES, Theme

logger = logging.getLogger(__name__)


def _load_saved_name() -> str:
    try:
        from src.core import prefs
        return prefs.get_theme()
    except Exception:
        return "light"


class ThemeManager(QObject):
    changed = Signal(object)  # emits the new Theme

    def __init__(self):
        super().__init__()
        name = _load_saved_name()
        self._theme: Theme = THEMES.get(name, LIGHT)
        self._bound = weakref.WeakKeyDictionary()  # widget -> style factory

    @property
    def theme(self) -> Theme:
        return self._theme

    def set_theme(self, name: str, persist: bool = True) -> None:
        theme = THEMES.get(name, LIGHT)
        if theme is self._theme:
            return
        self._theme = theme
        self.apply()
        if persist:
            self._save(theme.name)
        self.changed.emit(theme)

    def toggle(self) -> None:
        self.set_theme("light" if self._theme is DARK else "dark")

    def apply(self) -> None:
        """(Re)install the global stylesheet and re-evaluate every bound style."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(self._theme))
        for widget, factory in list(self._bound.items()):
            try:
                widget.setStyleSheet(factory())
            except RuntimeError:  # underlying C++ widget already deleted
                pass

    def bind(self, widget, factory: Callable[[], str]) -> None:
        self._bound[widget] = factory
        widget.setStyleSheet(factory())

    def _save(self, name: str) -> None:
        try:
            from src.core import prefs
            prefs.set_value("theme", name)
        except Exception:
            logger.exception("Could not persist theme preference")


manager = ThemeManager()


def current() -> Theme:
    return manager.theme


def bind_style(widget, factory: Callable[[], str]) -> None:
    """Apply a stylesheet built by `factory()` now and again whenever the theme changes."""
    manager.bind(widget, factory)
