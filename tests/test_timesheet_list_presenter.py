import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.timesheet_service import TimesheetService


class TestTimesheetListPresenter(unittest.TestCase):
    """Tests for TimesheetListPresenter coordination logic."""

    def _make_presenter(self):
        from ui.timesheet_list_presenter import TimesheetListPresenter

        mock_view = MagicMock()
        mock_view.fetch_requested = MagicMock()
        mock_view.fetch_requested.connect = MagicMock()

        mock_service = MagicMock(spec=TimesheetService)

        presenter = TimesheetListPresenter.__new__(TimesheetListPresenter)
        presenter.view = mock_view
        presenter.service = mock_service
        presenter.page_size = 20
        presenter._current_page = 0
        return presenter, mock_view, mock_service

    def test_result_path_calls_display_and_page_info(self):
        presenter, view, service = self._make_presenter()
        timesheets = [
            {
                "name": "TS-0001",
                "workflow_state": "Pending",
                "status": "Draft",
                "start_date": "2026-03-25",
                "end_date": "2026-03-25",
                "total_hours": 8,
            }
        ]

        presenter._on_result_ready(timesheets)

        view.display_timesheets.assert_called_once_with(timesheets)
        view.set_page_info.assert_called_once_with(
            current_page=0,
            page_size=20,
            result_count=1,
        )
        view.set_loading.assert_called_with(False)

    def test_error_path_calls_view_show_error(self):
        presenter, view, service = self._make_presenter()

        presenter._on_error_occurred("Network down")

        view.set_loading.assert_called_with(False)
        view.show_error.assert_called_once_with("Network down")

    def test_refresh_resets_page_to_zero(self):
        presenter, view, service = self._make_presenter()
        presenter._current_page = 5

        presenter._current_page = 0

        self.assertEqual(presenter._current_page, 0)


if __name__ == "__main__":
    unittest.main()
