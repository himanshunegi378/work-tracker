"""Compatibility layer over src.ui.design. New code should import from src.ui.design.

COLORS is a live mapping: it always reflects the active theme, so f-strings that
read it must be re-evaluated on theme change (use design.bind_style).
"""

from collections.abc import Mapping

from src.ui.design.manager import current

_ALIASES = {
    "bg": "bg",
    "card": "surface",
    "border": "border",
    "primary": "accent",
    "primary_hover": "accent_hover",
    "primary_hov": "accent_hover",
    "success": "success",
    "danger": "danger",
    "danger_hover": "danger_hover",
    "text_dark": "text",
    "text_body": "text_secondary",
    "text_muted": "text_muted",
    "text_subtle": "text_muted",
    "disabled": "text_disabled",
    "surface_alt": "surface_alt",
    "accent_soft": "accent_soft",
    "warning": "warning",
}


class _LiveColors(Mapping):
    def __getitem__(self, key):
        return getattr(current(), _ALIASES[key])

    def __iter__(self):
        return iter(_ALIASES)

    def __len__(self):
        return len(_ALIASES)


COLORS = _LiveColors()
RADIUS_CARD = 12
RADIUS_BUTTON = 8


def card_style(object_name: str) -> str:
    c = COLORS
    return f"""
        QFrame#{object_name} {{
            background-color: {c["card"]};
            border: 1px solid {c["border"]};
            border-radius: {RADIUS_CARD}px;
        }}
        QFrame#{object_name} QLabel {{
            background: transparent;
            border: none;
            padding: 0;
        }}
    """
