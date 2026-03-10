from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, 
    QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize

class SidebarView(QFrame):
    """A vertical navigation sidebar for switching between main application modules."""
    nav_requested = Signal(str)  # Emits the module name: "home", "projects", or "logs"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedWidth(70)
        self.setStyleSheet("""
            SidebarView {
                background-color: #263238;
                border: none;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #B0BEC5;
                padding: 15px 0px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #37474F;
                color: white;
            }
            QPushButton[active="true"] {
                background-color: #37474F;
                color: #2196F3;
                border-left: 3px solid #2196F3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        # Navigation Buttons
        self.home_btn = self._create_nav_item("🏠", "HOME", "home")
        self.project_btn = self._create_nav_item("📁", "PROJECTS", "projects")
        self.log_btn = self._create_nav_item("📋", "LOGS", "logs")

        layout.addWidget(self.home_btn)
        layout.addWidget(self.project_btn)
        layout.addWidget(self.log_btn)
        layout.addStretch()

        # Set default active
        self.set_active("home")

    def _create_nav_item(self, icon: str, label: str, module_id: str) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        
        btn_layout = QVBoxLayout(btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
        
        txt_lbl = QLabel(label)
        txt_lbl.setAlignment(Qt.AlignCenter)
        txt_lbl.setStyleSheet("font-size: 9px; background: transparent;")

        btn_layout.addWidget(icon_lbl)
        btn_layout.addWidget(txt_lbl)

        btn.clicked.connect(lambda: self.nav_requested.emit(module_id))
        return btn

    def set_active(self, module_id: str):
        """Visually updates which navigation item is selected."""
        self.home_btn.setProperty("active", str(module_id == "home").lower())
        self.project_btn.setProperty("active", str(module_id == "projects").lower())
        self.log_btn.setProperty("active", str(module_id == "logs").lower())
        
        # Refresh stylesheet to apply property-based styles
        self.style().unpolish(self.home_btn)
        self.style().polish(self.home_btn)
        self.style().unpolish(self.project_btn)
        self.style().polish(self.project_btn)
        self.style().unpolish(self.log_btn)
        self.style().polish(self.log_btn)
