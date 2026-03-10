from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QMessageBox
)
from ui.form_builder import DynamicForm
from services.project_manager import ProjectManager

class ProjectView(QMainWindow):
    """
    Architectural View for managing projects.
    Decoupled from models through the DynamicForm configuration.
    """
    def __init__(self, project_manager: ProjectManager):
        super().__init__()
        self.pm = project_manager
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Work Tracker - Add Project")
        self.setMinimumSize(400, 300)

        main_widget = QWidget()
        self.layout = QVBoxLayout(main_widget)
        
        title = QLabel("Add New Project")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        self.layout.addWidget(title)

        # Attribute-driven configuration
        # Adding a new field here automatically adds it to the UI
        project_config = {
            "name": {"label": "Project Name", "type": "text"},
            "description": {"label": "Description", "type": "textarea"},
            "status": {
                "label": "Initial Status", 
                "type": "select", 
                "options": ["active", "completed", "on-hold", "planned"]
            }
        }

        self.form = DynamicForm(project_config)
        self.form.form_submitted.connect(self._handle_submission)
        self.layout.addWidget(self.form)
        
        self.setCentralWidget(main_widget)

    def _handle_submission(self, data: dict):
        try:
            # Validation: basic check
            if not data["name"].strip():
                QMessageBox.warning(self, "Error", "Project Name is required!")
                return

            # Persist via service
            self.pm.add_project(
                name=data["name"],
                description=data["description"],
                status=data["status"]
            )
            
            QMessageBox.information(self, "Success", f"Project '{data['name']}' added!")
            self.form.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Failure", f"Failed to save: {str(e)}")
