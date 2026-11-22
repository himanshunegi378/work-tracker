"""Dropdown that picks whose data a list shows: you, everyone you may see, or one person."""

from typing import Dict, List

from PySide6.QtWidgets import QComboBox

ME, EVERYONE = "", "*"  # selected_employee() values besides a specific employee id


class EmployeeFilter(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItem("Me", ME)
        self.addItem("Everyone", EVERYONE)
        self.setMinimumWidth(160)

    def selected_employee(self) -> str:
        """"" for yourself, "*" for everyone you may see, else one employee's id."""
        data = self.currentData()
        return ME if data is None else str(data)

    def set_people(self, people: List[Dict[str, str]]) -> None:
        """Add the other people after Me / Everyone, keeping the current choice and emitting nothing."""
        current = self.selected_employee()
        self.blockSignals(True)
        while self.count() > 2:
            self.removeItem(2)
        for person in people:
            self.addItem(person["employee_name"], person["employee"])
        index = {ME: 0, EVERYONE: 1}.get(current, self.findData(current))
        self.setCurrentIndex(max(index, 0))
        self.blockSignals(False)
