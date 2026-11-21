"""Generates the application-wide stylesheet from design tokens.

QSS has no variables, so we template it here. Variants are expressed with Qt
dynamic properties (e.g. QPushButton[variant="primary"]) and cards with an
object-name-free property (QFrame[card="true"]) so no widget needs its own
stylesheet.
"""

from src.ui.design.tokens import FONT, FONT_SANS, FONT_SERIF, RADIUS, SPACE, Theme


def build_stylesheet(t: Theme) -> str:
    return f"""
    /* ── Base ─────────────────────────────────────────────────────── */
    QWidget {{ font-family: {FONT_SANS}; }}
    QMainWindow, QDialog, QStackedWidget {{ background-color: {t.bg}; color: {t.text}; }}
    QMessageBox {{ background-color: {t.surface}; }}
    QMessageBox QLabel {{ color: {t.text}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {t.text_disabled}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 4px; min-width: 28px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QCheckBox {{ color: {t.text_secondary}; spacing: {SPACE['sm']}px; }}
    QMenu {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; padding: 4px; }}
    QMenu::item:selected {{ background: {t.accent_soft}; color: {t.text}; }}

    /* ── Typography roles ─────────────────────────────────────────── */
    QLabel[role="display"]  {{ font-family: {FONT_SERIF}; font-size: {FONT['display']}px; font-weight: 700; color: {t.text}; }}
    QLabel[role="title"]    {{ font-family: {FONT_SERIF}; font-size: {FONT['title']}px; font-weight: 700; color: {t.text}; }}
    QLabel[role="heading"]  {{ font-family: {FONT_SERIF}; font-size: {FONT['heading']}px; font-weight: 700; color: {t.text}; }}
    QLabel[role="body"]     {{ font-size: {FONT['body']}px;    color: {t.text_secondary}; }}
    QLabel[role="caption"]  {{ font-size: {FONT['caption']}px; color: {t.text_muted}; }}
    QLabel[role="overline"] {{ font-size: {FONT['micro']}px;   font-weight: 700; color: {t.text_muted}; }}
    QLabel[role="metric"]   {{ font-size: 28px; font-weight: 700; font-family: {FONT_SERIF}; color: {t.text}; }}
    QLabel[tone="accent"]   {{ color: {t.accent}; }}
    QLabel[tone="success"]  {{ color: {t.success}; }}
    QLabel[tone="danger"]   {{ color: {t.danger}; }}

    /* ── Card surface (children stay unboxed) ─────────────────────── */
    QFrame[card="true"] {{
        background-color: {t.surface};
        border: 1px solid {t.border};
        border-radius: {RADIUS['lg']}px;
    }}
    QFrame[card="true"] QLabel {{ background: transparent; border: none; padding: 0; }}

    /* ── Buttons ──────────────────────────────────────────────────── */
    QPushButton[variant] {{
        border-radius: {RADIUS['md']}px;
        padding: {SPACE['sm']}px {SPACE['lg']}px;
        font-weight: 700;
        font-size: {FONT['body']}px;
        border: 1px solid transparent;
    }}
    QPushButton[variant="primary"] {{ background-color: {t.accent}; color: {t.text_on_accent}; }}
    QPushButton[variant="primary"]:hover {{ background-color: {t.accent_hover}; }}
    QPushButton[variant="success"] {{ background-color: {t.success}; color: {t.text_on_accent}; }}
    QPushButton[variant="success"]:hover {{ background-color: {t.success_hover}; }}
    QPushButton[variant="danger"] {{ background-color: {t.danger}; color: {t.text_on_accent}; }}
    QPushButton[variant="danger"]:hover {{ background-color: {t.danger_hover}; }}
    QPushButton[variant="secondary"] {{
        background-color: {t.surface}; color: {t.accent}; border: 1px solid {t.accent};
    }}
    QPushButton[variant="secondary"]:hover {{ background-color: {t.accent_soft}; }}
    QPushButton[variant]:disabled {{
        background-color: {t.surface_alt}; color: {t.text_disabled}; border-color: {t.border};
    }}

    /* ── Inputs ───────────────────────────────────────────────────── */
    QLineEdit, QComboBox {{
        background-color: {t.surface};
        border: 1px solid {t.border};
        border-radius: {RADIUS['md']}px;
        padding: {SPACE['sm']}px {SPACE['md']}px;
        color: {t.text};
        selection-background-color: {t.accent};
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t.accent}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {t.text_disabled}; background: {t.surface_alt}; }}

    /* ── Tooltips ─────────────────────────────────────────────────── */
    QToolTip {{
        background-color: {t.text}; color: {t.surface};
        border: none; padding: {SPACE['xs']}px {SPACE['sm']}px;
    }}
    """
