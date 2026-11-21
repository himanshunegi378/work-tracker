"""Design tokens: the single source of truth for color, type, space and shape.

Two layers:
  * PRIMITIVES - raw palette values ("Warm Architect": paper, clay, terracotta, sage).
  * Theme      - semantic roles (surface, text, accent...) that point at primitives.

Widgets and stylesheets reference semantic roles only, so a theme is just another
Theme instance and no view needs to change.
"""

from dataclasses import dataclass

PRIMITIVES = {
    # paper (light neutrals, warm)
    "paper-50": "#FFFDF9",
    "paper-100": "#F6F1EA",
    "paper-200": "#EFE7DC",
    "paper-300": "#E3D8C8",
    "paper-400": "#C9BBAA",
    # ink (text, warm browns)
    "ink-500": "#8C7B6D",
    "ink-700": "#5C4F45",
    "ink-900": "#2B2420",
    # terracotta (brand)
    "clay-100": "#F6E3D9",
    "clay-500": "#C25E3D",
    "clay-600": "#A94E31",
    # sage / brick / ochre (status)
    "sage-500": "#5E8C61",
    "sage-600": "#4B7350",
    "brick-500": "#B4483A",
    "brick-600": "#983B2F",
    "ochre-500": "#C98A2B",
    # charcoal (dark neutrals, warm)
    "char-900": "#1C1815",
    "char-800": "#26211D",
    "char-700": "#302A25",
    "char-600": "#3D352E",
    "char-500": "#5E5248",
    "bone-100": "#F1E9DF",
    "bone-300": "#CFC2B3",
    "bone-500": "#9A8B7C",
    # dark-mode brand/status
    "clay-400": "#E07A55",
    "clay-300": "#EE8E6B",
    "clay-900": "#3A2A22",
    "sage-300": "#8DB48F",
    "sage-400": "#A3C4A5",
    "brick-300": "#E0705F",
    "brick-400": "#EA8A7B",
    "ochre-300": "#E0A94F",
}

P = PRIMITIVES


@dataclass(frozen=True)
class Theme:
    name: str
    # surfaces
    bg: str
    surface: str
    surface_alt: str
    border: str
    # text
    text: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    text_on_accent: str
    # brand / state
    accent: str
    accent_hover: str
    accent_soft: str
    success: str
    success_hover: str
    danger: str
    danger_hover: str
    warning: str
    # sidebar rail
    rail_bg: str
    rail_hover: str
    rail_active: str


LIGHT = Theme(
    name="light",
    bg=P["paper-100"], surface=P["paper-50"], surface_alt=P["paper-200"], border=P["paper-300"],
    text=P["ink-900"], text_secondary=P["ink-700"], text_muted=P["ink-500"],
    text_disabled=P["paper-400"], text_on_accent=P["paper-50"],
    accent=P["clay-500"], accent_hover=P["clay-600"], accent_soft=P["clay-100"],
    success=P["sage-500"], success_hover=P["sage-600"],
    danger=P["brick-500"], danger_hover=P["brick-600"], warning=P["ochre-500"],
    rail_bg=P["paper-200"], rail_hover=P["paper-300"], rail_active=P["clay-500"],
)

DARK = Theme(
    name="dark",
    bg=P["char-900"], surface=P["char-800"], surface_alt=P["char-700"], border=P["char-600"],
    text=P["bone-100"], text_secondary=P["bone-300"], text_muted=P["bone-500"],
    text_disabled=P["char-500"], text_on_accent=P["char-900"],
    accent=P["clay-400"], accent_hover=P["clay-300"], accent_soft=P["clay-900"],
    success=P["sage-300"], success_hover=P["sage-400"],
    danger=P["brick-300"], danger_hover=P["brick-400"], warning=P["ochre-300"],
    rail_bg=P["char-800"], rail_hover=P["char-700"], rail_active=P["clay-400"],
)

THEMES = {"light": LIGHT, "dark": DARK}

# Spacing scale (px) - 4px base.
SPACE = {"xxs": 2, "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

# Corner radii (px)
RADIUS = {"sm": 6, "md": 8, "lg": 12, "pill": 999}

# Typography. Headings are serif for the "architect's notebook" feel.
FONT_SERIF = "'Georgia', 'Noto Serif', 'DejaVu Serif', serif"
FONT_SANS = "'Inter', 'Noto Sans', 'Segoe UI', 'Helvetica Neue', sans-serif"
FONT = {"display": 28, "title": 22, "heading": 17, "body": 13, "caption": 12, "micro": 11}
