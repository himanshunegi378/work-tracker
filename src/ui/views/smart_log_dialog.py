from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QHBoxLayout, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem


class SmartLogDialog(QDialog):
    """
    A minimalist logging popup with smart defaults.

    Accepts a pre-fetched list of project names so no second API call is
    needed when the scheduler fires. Names are cached by HomePresenter and
    passed in at construction time.

    Args:
        project_names: List of project name strings (from HomePresenter cache).
        lm:            LogManager for reading the last log and saving new ones.
        parent:        Parent widget (pass None to allow display when minimized).
    """

    def __init__(
        self,
        project_options: List[Dict[str, str]],
        activity_names: List[str],
        smart_defaults: Optional[Dict[str, object]] = None,
        parent=None,
        activity_status_message: Optional[str] = None,
    ):
        super().__init__(parent)
        self._project_options = project_options
        self._activity_names = activity_names
        self._smart_defaults = smart_defaults or {}
        self._activity_status_message = activity_status_message
        self.setWindowTitle("Log Your Progress")
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()
        self._load_smart_defaults()
        self.raise_()
        self.activateWindow()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("What are you working on?")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        form = QFormLayout()

        # Project selection — populated from the pre-fetched list
        self.project_cb = QComboBox()
        for option in self._project_options:
            self.project_cb.addItem(option["name"], option["id"])
        if not self._project_options:
            self.project_cb.addItem("(no projects loaded)")

        # Log description
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Task description…")

        self.activity_cb = QComboBox()
        self.activity_cb.setEditable(True)
        self.activity_cb.setInsertPolicy(QComboBox.NoInsert)
        self.activity_cb.setPlaceholderText("Select or search activity…")
        self.activity_cb.setEnabled(bool(self._activity_names))

        self._activity_model = QStandardItemModel(self.activity_cb)
        self._set_activity_options(self._activity_names)
        self.activity_cb.setModel(self._activity_model)
        self.activity_cb.lineEdit().textEdited.connect(self._filter_activities)
        self.activity_cb.lineEdit().selectionChanged.connect(self._show_all_activities)
        self.activity_cb.lineEdit().setClearButtonEnabled(True)

        self.billable_cb = QCheckBox("Billable")

        form.addRow("Project:", self.project_cb)
        form.addRow("Activity:", self.activity_cb)
        form.addRow("Doing:",   self.desc_input)
        form.addRow("", self.billable_cb)
        layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        if self._activity_status_message:
            self.status_label.setText(self._activity_status_message)
            self.status_label.setStyleSheet("color: #C62828; font-size: 12px;")
            self.status_label.show()
        elif not self._activity_names:
            self.status_label.setText("Activity options are unavailable right now.")
            self.status_label.setStyleSheet("color: #C62828; font-size: 12px;")
            self.status_label.show()

        # Action buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Skip")
        cancel_btn.clicked.connect(self.reject)

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
        self.save_btn.setEnabled(bool(self._activity_names))

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def _load_smart_defaults(self) -> None:
        """Pre-fill from latest timesheet-backed smart-log state when available."""
        project_name = str(self._smart_defaults.get("project_name") or "")
        activity_name = str(self._smart_defaults.get("activity_name") or "")
        description = str(self._smart_defaults.get("description") or "")

        if project_name or activity_name or description:
            idx = self.project_cb.findText(project_name)
            if idx >= 0:
                self.project_cb.setCurrentIndex(idx)

            activity_idx = self.activity_cb.findText(activity_name)
            if activity_idx >= 0:
                self.activity_cb.setCurrentIndex(activity_idx)
            elif activity_name:
                self.activity_cb.lineEdit().setText(activity_name)

            self.desc_input.setText(description)
            self.billable_cb.setChecked(bool(self._smart_defaults.get("is_billable")))
            self.desc_input.selectAll()
            self.desc_input.setFocus()
        elif self._activity_names:
            self.activity_cb.lineEdit().setText("")
            self.billable_cb.setChecked(False)

    def _set_activity_options(self, activity_names: List[str]) -> None:
        self._activity_model.clear()
        for name in activity_names:
            self._activity_model.appendRow(QStandardItem(name))

    def _show_all_activities(self) -> None:
        if self.activity_cb.lineEdit().hasSelectedText():
            return
        self._set_activity_options(self._activity_names)

    def _filter_activities(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            filtered = self._activity_names
        else:
            filtered = [name for name in self._activity_names if query in name.lower()]
        self._set_activity_options(filtered)
        self.activity_cb.showPopup()

    def _on_save(self) -> None:
        project = self.project_cb.currentText()
        project_id = self.project_cb.currentData()
        activity = self.activity_cb.currentText().strip()
        desc    = self.desc_input.text().strip()
        if (
            not project
            or not project_id
            or not activity
            or not desc
            or activity not in self._activity_names
            or project == "(no projects loaded)"
        ):
            return
        self._submission = {
            "project_id": str(project_id),
            "project_name": project,
            "activity_name": activity,
            "description": desc,
            "is_billable": self.billable_cb.isChecked(),
        }
        self.accept()

    def get_submission(self) -> Optional[Dict[str, object]]:
        """Return the structured smart-log payload captured from the dialog."""
        return getattr(self, "_submission", None)

    def set_error_message(self, message: str) -> None:
        """Show a save/fetch error message in the dialog footer."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #C62828; font-size: 12px;")
        self.status_label.show()
