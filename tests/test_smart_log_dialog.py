import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from src.ui.views.smart_log_dialog import SmartLogDialog


class TestSmartLogDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_disabled_when_activity_cache_missing(self):
        dialog = SmartLogDialog(
            [{"id": "PROJ-1", "name": "Project A"}],
            [],
        )

        self.assertFalse(dialog.save_btn.isEnabled())
        self.assertFalse(dialog.status_label.isHidden())

    def test_filter_activities_reduces_visible_options(self):
        dialog = SmartLogDialog(
            [{"id": "PROJ-1", "name": "Project A"}],
            ["Code Review", "Testing", "Documentation"],
        )

        dialog._filter_activities("test")

        self.assertEqual(dialog._activity_model.rowCount(), 1)
        self.assertEqual(dialog._activity_model.item(0).text(), "Testing")

    def test_smart_defaults_prefill_project_activity_description_and_billable(self):
        dialog = SmartLogDialog(
            [
                {"id": "PROJ-1", "name": "Project A"},
                {"id": "PROJ-2", "name": "Project B"},
            ],
            ["Code Review", "Testing"],
            smart_defaults={
                "project_name": "Project B",
                "activity_name": "Code Review",
                "description": "Finish auth flow",
                "is_billable": True,
            },
        )

        self.assertEqual(dialog.project_cb.currentText(), "Project B")
        self.assertEqual(dialog.activity_cb.currentText(), "Code Review")
        self.assertEqual(dialog.desc_input.text(), "Finish auth flow")
        self.assertTrue(dialog.billable_cb.isChecked())

    def test_save_requires_valid_activity(self):
        dialog = SmartLogDialog(
            [{"id": "PROJ-1", "name": "Project A"}],
            ["Code Review", "Testing"],
        )
        dialog.project_cb.setCurrentText("Project A")
        dialog.activity_cb.lineEdit().setText("Unknown")
        dialog.desc_input.setText("Worked on a task")

        dialog._on_save()

        self.assertIsNone(dialog.get_submission())

    def test_save_returns_structured_submission(self):
        dialog = SmartLogDialog(
            [{"id": "PROJ-1", "name": "Project A"}],
            ["Code Review", "Testing"],
        )
        dialog.project_cb.setCurrentIndex(0)
        dialog.activity_cb.setCurrentText("Code Review")
        dialog.desc_input.setText("Worked on a task")
        dialog.billable_cb.setChecked(True)

        dialog._on_save()

        self.assertEqual(
            dialog.get_submission(),
            {
                "project_id": "PROJ-1",
                "project_name": "Project A",
                "activity_name": "Code Review",
                "description": "Worked on a task",
                "is_billable": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
