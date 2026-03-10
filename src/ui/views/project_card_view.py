from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from models.project import Project

class ProjectCard(QFrame):
    """A styled card representing a single project in the dashboard."""
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            ProjectCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
            ProjectCard:hover {
                border: 1px solid #2196F3;
                background-color: #f5faff;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header: Name and Status
        header_layout = QHBoxLayout()
        name_label = QLabel(self.project.name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        
        status_label = QLabel(self.project.status.upper())
        status_color = "#4CAF50" if self.project.status == "active" else "#9E9E9E"
        status_label.setStyleSheet(f"""
            color: white; 
            background-color: {status_color}; 
            border-radius: 4px; 
            padding: 2px 6px; 
            font-size: 10px;
            font-weight: bold;
        """)
        
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(status_label)
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(self.project.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 5px;")
        layout.addWidget(desc_label)
