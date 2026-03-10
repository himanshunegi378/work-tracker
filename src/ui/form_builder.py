from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QTextEdit, QComboBox, QPushButton, QLabel
)
from PySide6.QtCore import Signal
from typing import Dict, Any, List

class DynamicForm(QWidget):
    """
    A generic form builder that creates fields based on a configuration dictionary.
    Configuration format:
    {
        "field_id": {"label": "Display Name", "type": "text/textarea/select", "options": []}
    }
    """
    form_submitted = Signal(dict)

    def __init__(self, config: Dict[str, Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.config = config
        self.fields = {}
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        for field_id, props in self.config.items():
            label = props.get("label", field_id.capitalize())
            field_type = props.get("type", "text")
            
            widget = self._create_widget(field_type, props)
            self.form_layout.addRow(label, widget)
            self.fields[field_id] = widget

        self.layout.addLayout(self.form_layout)

        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self._on_submit)
        self.layout.addWidget(self.submit_btn)

    def _create_widget(self, field_type: str, props: Dict[str, Any]) -> QWidget:
        if field_type == "textarea":
            return QTextEdit()
        elif field_type == "select":
            cb = QComboBox()
            cb.addItems(props.get("options", []))
            return cb
        else:
            return QLineEdit()

    def _get_value(self, field_id: str) -> Any:
        widget = self.fields[field_id]
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        return None

    def _on_submit(self):
        data = {fid: self._get_value(fid) for fid in self.config.keys()}
        self.form_submitted.emit(data)

    def clear(self):
        for widget in self.fields.values():
            if isinstance(widget, (QLineEdit, QTextEdit)):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
