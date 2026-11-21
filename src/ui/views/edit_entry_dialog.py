"""Dialog to change one time-log entry of a Pending timesheet."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QTimeEdit, QVBoxLayout, QWidget,
)

from src.ui.design import SPACE, button, label


def _parse(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


class EditEntryDialog(QDialog):
    """Edit description, project, activity, billable flag and start/end time of one entry."""

    def __init__(
        self,
        entry: Dict[str, Any],
        projects: List[Dict[str, Any]],
        activities: List[str],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle(f"Edit entry #{entry.get('idx') or ''}".strip())
        self.setMinimumWidth(460)
        self.setModal(True)

        self._start = _parse(entry.get("from_time"))
        self._end = _parse(entry.get("to_time"))
        day = f"{self._start:%Y-%m-%d}" if self._start else ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        layout.setSpacing(SPACE["md"])
        layout.addWidget(label("Edit entry", "title"))
        if day:
            layout.addWidget(label(day, "caption"))

        form = QFormLayout()
        form.setSpacing(SPACE["sm"])

        self.project_combo = QComboBox()
        current_project = str(entry.get("project") or "")
        seen = set()
        for project in projects:
            pid = str(project.get("id") or "")
            if pid and pid not in seen:
                seen.add(pid)
                self.project_combo.addItem(f"{pid} · {project.get('name')}", (pid, str(project.get("name") or "")))
        if current_project and current_project not in seen:  # keep a project the list does not include
            self.project_combo.insertItem(
                0, f"{current_project} · {entry.get('project_name') or ''}",
                (current_project, str(entry.get("project_name") or "")),
            )
        index = self.project_combo.findData((current_project, str(entry.get("project_name") or "")))
        if index < 0:
            index = next((i for i in range(self.project_combo.count())
                          if self.project_combo.itemData(i)[0] == current_project), 0)
        self.project_combo.setCurrentIndex(index)

        self.activity_combo = QComboBox()
        names = list(dict.fromkeys(activities))
        current_activity = str(entry.get("activity_type") or "")
        if current_activity and current_activity not in names:
            names.insert(0, current_activity)
        self.activity_combo.addItems(names)
        self.activity_combo.setCurrentText(current_activity)

        self.description_input = QLineEdit(str(entry.get("description") or ""))
        self.billable_check = QCheckBox("Billable")
        self.billable_check.setChecked(bool(entry.get("is_billable")))

        self.from_edit = QTimeEdit(QTime(self._start.hour, self._start.minute) if self._start else QTime(0, 0))
        self.to_edit = QTimeEdit(QTime(self._end.hour, self._end.minute) if self._end else QTime(0, 0))
        for edit in (self.from_edit, self.to_edit):
            edit.setDisplayFormat("HH:mm")
        times = QHBoxLayout()
        times.addWidget(self.from_edit)
        times.addWidget(label("to", "caption"))
        times.addWidget(self.to_edit)

        form.addRow("Project", self.project_combo)
        form.addRow("Activity", self.activity_combo)
        form.addRow("Description", self.description_input)
        form.addRow("Time", times)
        form.addRow("", self.billable_check)
        layout.addLayout(form)

        self.error = label("", "caption", tone="danger")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)

        row = QHBoxLayout()
        row.addStretch()
        self.cancel_btn = button("Cancel", "secondary")
        self.save_btn = button("Save", "primary")
        self.save_btn.setDefault(True)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.save_btn)
        layout.addLayout(row)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._on_save)

    def _on_save(self) -> None:
        problem = self.validate()
        if problem:
            self.error.setText(problem)
            self.error.show()
            return
        self.accept()

    def _times(self):
        if not self._start:
            return None, None
        start = datetime.combine(self._start.date(), self.from_edit.time().toPython())
        end = datetime.combine(self._start.date(), self.to_edit.time().toPython())
        return start, end

    def validate(self) -> str:
        if not self.description_input.text().strip():
            return "Description cannot be empty."
        start, end = self._times()
        if start and end and end <= start:
            return "The end time must be after the start time."
        return ""

    def get_changes(self) -> Dict[str, Any]:
        """Only the fields that differ from the original entry, keyed like `update_time_log`."""
        changes: Dict[str, Any] = {}
        description = self.description_input.text().strip()
        if description != str(self.entry.get("description") or "").strip():
            changes["description"] = description
        if self.activity_combo.currentText() != str(self.entry.get("activity_type") or ""):
            changes["activity"] = self.activity_combo.currentText()
        project = self.project_combo.currentData()
        if project and project[0] != str(self.entry.get("project") or ""):
            changes["project_id"], changes["project_name"] = project
        if self.billable_check.isChecked() != bool(self.entry.get("is_billable")):
            changes["is_billable"] = self.billable_check.isChecked()
        start, end = self._times()
        if start and self._start and start != self._start.replace(second=0, microsecond=0):
            changes["from_time"] = start
        if end and self._end and end != self._end.replace(second=0, microsecond=0):
            changes["to_time"] = end
        return changes
