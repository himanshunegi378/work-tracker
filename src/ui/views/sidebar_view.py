from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.ui.design import bind_style, current, manager
from src.ui.icons import make_icon


NAV_ITEMS = [
    ("home", "HOME", "home"),
    ("projects", "PROJECTS", "projects"),
    ("activities", "ACTIVITIES", "activities"),
    ("timesheets", "TIMESHEETS", "timesheets"),
    ("leave", "LEAVE", "leave"),
    ("settings", "SETTINGS", "settings"),
]


class _Sand:
    """Live view of the sidebar palette: always reflects the active theme."""

    _MAP = {
        "rail_bg": "rail_bg", "rail_border": "border", "item_fg": "text_muted",
        "item_hover_bg": "rail_hover", "item_hover_fg": "rail_active",
        "item_active_fg": "rail_active", "item_active_border": "rail_active",
        "caption_fg": "text_muted", "header_bg": "rail_hover", "header_fg": "text_secondary",
        "badge_bg": "accent", "badge_fg": "text_on_accent",
    }

    def __getitem__(self, key):
        return getattr(current(), self._MAP[key])


SAND_THEME = _Sand()


class NavItemView(QFrame):
    clicked = Signal(str)

    def __init__(self, icon: str, label: str, module_id: str, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        self.icon_name = icon
        self.setObjectName("navItem")
        self.setProperty("active", "false")
        self._setup_ui(icon, label)

    def _setup_ui(self, icon: str, label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.body = QFrame()
        self.body.setObjectName("itemBody")
        self.body.setCursor(Qt.PointingHandCursor)
        self.body.setFixedWidth(72)

        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(6, 6, 6, 6)
        body_layout.setSpacing(0)

        self.halo = QFrame()
        self.halo.setObjectName("halo")
        halo_layout = QHBoxLayout(self.halo)
        halo_layout.setContentsMargins(4, 4, 4, 4)
        halo_layout.setSpacing(0)

        self.button = QPushButton()
        self.button.setIcon(make_icon(icon, SAND_THEME["item_fg"]))
        self.button.setIconSize(QSize(24, 24))
        self.button.setObjectName("iconButton")
        self.button.setCheckable(False)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setToolTip(label.title())
        self.button.setFixedSize(QSize(52, 52))
        self.button.clicked.connect(lambda: self.clicked.emit(self.module_id))
        self._active = False
        manager.changed.connect(lambda _t: self._refresh_icon())

        halo_layout.addStretch()
        halo_layout.addWidget(self.button)
        halo_layout.addStretch()

        body_layout.addWidget(self.halo)
        layout.addWidget(self.body)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.module_id)
        super().mousePressEvent(event)

    def _refresh_icon(self):
        try:
            color = SAND_THEME["item_active_fg"] if self._active else SAND_THEME["item_fg"]
            self.button.setIcon(make_icon(self.icon_name, color))
        except RuntimeError:  # widget already deleted
            pass

    def set_active(self, active: bool):
        active_value = str(active).lower()
        self.setProperty("active", active_value)
        self.body.setProperty("active", active_value)
        self.button.setProperty("active", active_value)
        self.halo.setProperty("active", active_value)
        self._active = active
        self._refresh_icon()

        for widget in (self, self.body, self.button, self.halo):
            self.style().unpolish(widget)
            self.style().polish(widget)


class SidebarView(QFrame):
    """Sand-themed sidebar finalized with the Badge Orbit active state."""

    nav_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("sidebarView")
        self.setFixedWidth(96)
        bind_style(self, self._build_stylesheet)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(10)

        for icon, label, module_id in NAV_ITEMS[:-1]:
            item = self._create_nav_item(icon, label, module_id)
            self.items[module_id] = item
            layout.addWidget(item)

        layout.addStretch()

        settings_item = self._create_nav_item(*NAV_ITEMS[-1])
        self.items["settings"] = settings_item
        layout.addWidget(settings_item)

        self.set_active("home")

    def _create_nav_item(self, icon: str, label: str, module_id: str) -> NavItemView:
        item = NavItemView(icon, label, module_id)
        item.clicked.connect(self.nav_requested.emit)
        return item

    def _build_stylesheet(self) -> str:
        return f"""
            QFrame#sidebarView {{
                background-color: {SAND_THEME["rail_bg"]};
                border: 1px solid {SAND_THEME["rail_border"]};
                border-radius: 24px;
            }}
            QFrame#navItem {{
                background: transparent;
                border: none;
            }}
            QFrame#itemBody {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 20px;
            }}
            QFrame#itemBody:hover {{
                background-color: {SAND_THEME["item_hover_bg"]};
            }}
            QFrame#halo {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 18px;
            }}
            QPushButton#iconButton {{
                background-color: transparent;
                color: {SAND_THEME["item_fg"]};
                border: 1px solid transparent;
                border-radius: 16px;
                padding: 0px;
                font-size: 20px;
                font-weight: 700;
            }}
            QPushButton#iconButton:hover {{
                color: {SAND_THEME["item_hover_fg"]};
            }}
            QFrame#navItem[active="true"] QPushButton#iconButton {{
                background-color: transparent;
                color: {SAND_THEME["item_active_fg"]};
                border: 2px solid {SAND_THEME["item_active_border"]};
            }}
        """

    def set_active(self, module_id: str):
        for item_module_id, item in self.items.items():
            item.set_active(item_module_id == module_id)
