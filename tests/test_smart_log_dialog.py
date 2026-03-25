import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtWidgets import QApplication

from models.log import Log
from ui.views.smart_log_dialog import SmartLogDialog


class TestSmartLogDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_disabled_when_activity_cache_missing(self):
        log_manager = MagicMock()
        log_manager.get_last_log.return_value = None

        dialog = SmartLogDialog(["Project A"], [], log_manager)

        self.assertFalse(dialog.save_btn.isEnabled())
        self.assertTrue(dialog.status_label.isVisible())

    def test_filter_activities_reduces_visible_options(self):
        log_manager = MagicMock()
        log_manager.get_last_log.return_value = None

        dialog = SmartLogDialog(
            ["Project A"],
            ["Code Review", "Testing", "Documentation"],
            log_manager,
        )

        dialog._filter_activities("test")

        self.assertEqual(dialog._activity_model.rowCount(), 1)
        self.assertEqual(dialog._activity_model.item(0).text(), "Testing")

    def test_last_log_prefills_project_activity_and_description(self):
        log_manager = MagicMock()
        log_manager.get_last_log.return_value = Log(
            description="Finish auth flow",
            project_name="Project B",
            activity_name="Code Review",
        )

        dialog = SmartLogDialog(
            ["Project A", "Project B"],
            ["Code Review", "Testing"],
            log_manager,
        )

        self.assertEqual(dialog.project_cb.currentText(), "Project B")
        self.assertEqual(dialog.activity_cb.currentText(), "Code Review")
        self.assertEqual(dialog.desc_input.text(), "Finish auth flow")

    def test_save_requires_valid_activity(self):
        log_manager = MagicMock()
        log_manager.get_last_log.return_value = None

        dialog = SmartLogDialog(
            ["Project A"],
            ["Code Review", "Testing"],
            log_manager,
        )
        dialog.project_cb.setCurrentText("Project A")
        dialog.activity_cb.lineEdit().setText("Unknown")
        dialog.desc_input.setText("Worked on a task")

        dialog._on_save()

        log_manager.add_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
