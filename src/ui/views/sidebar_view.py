from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


NAV_ITEMS = [
    ("🏠", "HOME", "home"),
    ("📁", "PROJECTS", "projects"),
    ("⚡", "ACTIVITIES", "activities"),
    ("⏱️", "TIMESHEETS", "timesheets"),
    ("⚙️", "SETTINGS", "settings"),
]


SAND_THEME = {
    "rail_bg": "#F4EEE8",
    "rail_border": "#E8DCC4",
    "header_bg": "#EBDCCB",
    "header_fg": "#8C6B5D",
    "badge_bg": "#D97757",
    "badge_fg": "#FDFBF7",
    "item_fg": "#B09E8D",
    "item_hover_bg": "#EBDCCB",
    "item_hover_fg": "#C25E3D",
    "item_active_fg": "#C25E3D",
    "item_active_border": "#C25E3D",
    "caption_fg": "#B09E8D",
}


class NavItemView(QFrame):
    clicked = Signal(str)

    def __init__(self, icon: str, label: str, module_id: str, parent=None):
        super().__init__(parent)
        self.module_id = module_id
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

        self.button = QPushButton(icon)
        self.button.setObjectName("iconButton")
        self.button.setCheckable(False)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setToolTip(label.title())
        self.button.setFixedSize(QSize(52, 52))
        self.button.clicked.connect(lambda: self.clicked.emit(self.module_id))

        halo_layout.addStretch()
        halo_layout.addWidget(self.button)
        halo_layout.addStretch()

        body_layout.addWidget(self.halo)
        layout.addWidget(self.body)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.module_id)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        active_value = str(active).lower()
        self.setProperty("active", active_value)
        self.body.setProperty("active", active_value)
        self.button.setProperty("active", active_value)
        self.halo.setProperty("active", active_value)

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
        self.setStyleSheet(self._build_stylesheet())

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
