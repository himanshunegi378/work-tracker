import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from src.ui.views.timesheet_list_view import TimesheetListView


class TestTimesheetListView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_view(self):
        view = TimesheetListView()
        view.display_timesheets(
            [
                {
                    "name": "TS-0001",
                    "workflow_state": "Draft",
                    "status": "Open",
                    "start_date": "2026-07-08",
                    "end_date": "2026-07-08",
                    "total_hours": "4.5",
                },
                {
                    "name": "TS-0002",
                    "workflow_state": "Submitted",
                    "status": "Submitted",
                    "start_date": "2026-07-09",
                    "end_date": "2026-07-09",
                    "total_hours": 3,
                },
            ]
        )
        return view

    def test_search_filters_current_timesheet_page(self):
        view = self._make_view()

        view.search_input.setText("submitted")

        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 0).text(), "TS-0002")

    def test_status_filter_limits_visible_rows(self):
        view = self._make_view()

        view.status_filter.setCurrentText("Open")

        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 0).text(), "TS-0001")

    def test_summary_reflects_visible_page_hours_and_statuses(self):
        view = self._make_view()

        self.assertIn("Page total: 7.5 h", view.summary_lbl.text())
        self.assertIn("1 Open", view.summary_lbl.text())
        self.assertIn("1 Submitted", view.summary_lbl.text())

        view.search_input.setText("TS-0001")

        self.assertIn("Page total: 4.5 h", view.summary_lbl.text())
        self.assertIn("1 Open", view.summary_lbl.text())
        self.assertNotIn("Submitted", view.summary_lbl.text())


if __name__ == "__main__":
    unittest.main()
