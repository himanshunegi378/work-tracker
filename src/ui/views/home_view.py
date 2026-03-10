from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QScrollArea, QDialog, QFrame
)
from PySide6.QtCore import Qt, Signal
from ui.views.project_card_view import ProjectCard
from ui.views.project_add_qt_view import ProjectAddQtView
from models.project import Project
from typing import List

class HomeView(QWidget):
    """The main entry page of the application, architected for multi-project views."""
    add_project_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Header Section
        header = QHBoxLayout()
        title = QLabel("My Projects")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        
        self.add_btn = QPushButton("+ New Project")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.add_btn.clicked.connect(self.add_project_requested.emit)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.add_btn)
        self.layout.addLayout(header)

        # Main List Section (Scrollable Area)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(12)
        
        self.scroll.setWidget(self.list_container)
        self.layout.addWidget(self.scroll)

    def display_projects(self, projects: List[Project]):
        """Renders the grid of project cards."""
        # Clear existing list
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not projects:
            empty_label = QLabel("No projects found. Click '+ New Project' to get started!")
            empty_label.setStyleSheet("color: #999; font-size: 14px; margin-top: 50px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty_label)
            return

        for p in projects:
            card = ProjectCard(p)
            self.list_layout.addWidget(card)

class AddProjectDialog(QDialog):
    """A modal dialog to keep the UI clean and contextual."""
    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumSize(400, 350)
        
        layout = QVBoxLayout(self)
        self.add_view = ProjectAddQtView()
        layout.addWidget(self.add_view)
        
        # We'll need a presenter for this view inside the dialog
        from ui.presenter import ProjectAddPresenter
        self.presenter = ProjectAddPresenter(self.add_view, project_manager)
        self.add_view.submit_btn.clicked.connect(self.presenter.on_submit_clicked)
        
        # Close dialog on successful project creation
        # Since ProjectAddPresenter is 'dumb', let's manually close on click if we want
        # but better is to listen to a success signal if we added one. 
        # For now, keeping it simple.
