from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QTextEdit, QComboBox, QPushButton, QLabel, QMessageBox
)
from src.ui.contracts import ProjectAddViewInterface
from typing import Dict, Any

class ProjectAddQtView(QWidget, ProjectAddViewInterface):
    """
    A concrete 'Passive View' implementation in PySide.
    No business logic lives here.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.desc_input = QTextEdit()
        self.status_cb = QComboBox()
        self.status_cb.addItems(["active", "on-hold", "completed"])

        self.form_layout.addRow("Project Name:", self.name_input)
        self.form_layout.addRow("Description:", self.desc_input)
        self.form_layout.addRow("Status:", self.status_cb)

        self.submit_btn = QPushButton("Save Project")
        
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.submit_btn)

    # --- Implementation of View Contract ---
    
    def get_form_data(self) -> Dict[str, str]:
        return {
            "name": self.name_input.text(),
            "description": self.desc_input.toPlainText(),
            "status": self.status_cb.currentText()
        }

    def show_error(self, message: str):
        QMessageBox.warning(self, "Validation Error", message)

    def show_success(self, message: str):
        QMessageBox.information(self, "Success", message)

    def clear_form(self):
        self.name_input.clear()
        self.desc_input.clear()
        self.status_cb.setCurrentIndex(0)

    def set_loading(self, is_loading: bool):
        """Standard architectural pattern for loading state."""
        self.submit_btn.setEnabled(not is_loading)
        self.name_input.setReadOnly(is_loading)
        if is_loading:
            self.submit_btn.setText("Saving...")
        else:
            self.submit_btn.setText("Save Project")
