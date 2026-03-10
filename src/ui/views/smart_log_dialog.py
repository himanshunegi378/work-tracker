from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QPushButton, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt
from services.project_manager import ProjectManager
from services.log_manager import LogManager

class SmartLogDialog(QDialog):
    """
    A Toptal-style minimalist logging popup with smart defaults.
    """
    def __init__(self, pm: ProjectManager, lm: LogManager, parent=None):
        # We pass None as parent if we want it to be truly independent of minimized state,
        # but Qt.WindowStaysOnTopHint usually handles it.
        super().__init__(parent)
        self.pm = pm
        self.lm = lm
        self.setWindowTitle("Log Your Progress")
        self.setMinimumWidth(350)
        
        # Architecture: Ensure the window stays on top of all other apps
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self._setup_ui()
        self._load_smart_defaults()
        
        # Force activation
        self.raise_()
        self.activateWindow()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)

        title = QLabel("What are you working on?")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        self.layout.addWidget(title)

        form = QFormLayout()
        
        # Project Selection
        self.project_cb = QComboBox()
        projects = self.pm.get_all_projects()
        for p in projects:
            self.project_cb.addItem(p.name)
        
        # Log Description
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Task description...")

        form.addRow("Project:", self.project_cb)
        form.addRow("Doing:", self.desc_input)
        self.layout.addLayout(form)

        # Actions
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Skip")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Log Activity")
        self.save_btn.setDefault(True)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.save_btn.clicked.connect(self._on_save)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        self.layout.addLayout(btn_layout)

    def _load_smart_defaults(self):
        """Pre-fills fields with the last log's data (Smart Persistence)."""
        last_log = self.lm.get_last_log()
        if last_log:
            # Match project name in combo box
            idx = self.project_cb.findText(last_log.project_name)
            if idx >= 0:
                self.project_cb.setCurrentIndex(idx)
            
            # Pre-fill description
            self.desc_input.setText(last_log.description)
            self.desc_input.selectAll()  # Allow quick overwrite
            self.desc_input.setFocus()

    def _on_save(self):
        project = self.project_cb.currentText()
        desc = self.desc_input.text().strip()
        
        if not project or not desc:
            return # Basic validation: don't save empty logs

        self.lm.add_log(project, desc)
        self.accept()
