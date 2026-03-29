import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.timesheet_service import TimesheetService


class TestTimesheetModulePresenter(unittest.TestCase):
    def _make_presenter(self):
        from src.ui.timesheet_module_presenter import TimesheetModulePresenter

        mock_view = MagicMock()
        mock_view.list_view = MagicMock()
        mock_view.list_view.fetch_requested = MagicMock()
        mock_view.list_view.fetch_requested.connect = MagicMock()
        mock_view.list_view.timesheet_selected = MagicMock()
        mock_view.list_view.timesheet_selected.connect = MagicMock()
        mock_view.detail_view = MagicMock()
        mock_view.detail_view.back_requested = MagicMock()
        mock_view.detail_view.back_requested.connect = MagicMock()

        mock_service = MagicMock(spec=TimesheetService)

        presenter = TimesheetModulePresenter.__new__(TimesheetModulePresenter)
        presenter.view = mock_view
        presenter.service = mock_service
        presenter.list_presenter = MagicMock()
        presenter.detail_presenter = MagicMock()
        return presenter, mock_view, mock_service

    def test_refresh_shows_list_and_refreshes_list_presenter(self):
        presenter, view, service = self._make_presenter()

        presenter.refresh()

        view.show_list.assert_called_once_with()
        presenter.list_presenter.refresh.assert_called_once_with()

    def test_selecting_timesheet_shows_detail_and_loads_detail(self):
        presenter, view, service = self._make_presenter()

        presenter._on_timesheet_selected("TS-1")

        view.show_detail.assert_called_once_with()
        presenter.detail_presenter.load_timesheet.assert_called_once_with("TS-1")

    def test_back_returns_to_list(self):
        presenter, view, service = self._make_presenter()

        presenter._on_back_requested()

        view.show_list.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
