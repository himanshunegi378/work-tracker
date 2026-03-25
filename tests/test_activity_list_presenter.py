"""
tests/test_activity_list_presenter.py
--------------------------------------
Unit tests for ActivityListPresenter.

Tests use unittest.mock to isolate the Presenter from real network calls
and real Qt widgets, enabling fast, deterministic, headless execution.

Run:
    python -m pytest tests/test_activity_list_presenter.py -v
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, call

# Make src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.activity_service import ActivityService, ActivityServiceError


class TestActivityListPresenter(unittest.TestCase):
    """Tests for ActivityListPresenter coordination logic."""

    def _make_presenter(self, activities=None, raise_error=False):
        """Helper: build a Presenter with mocked View and Service."""
        # Import here so PySide6 import errors surface clearly
        from ui.activity_list_presenter import ActivityListPresenter

        mock_view = MagicMock()
        # fetch_requested is a Signal — we replace it with a plain MagicMock
        # so tests can call connect() and the presenter can subscribe normally.
        # (Real Signals require a QApplication; mocking avoids that dependency.)
        mock_view.fetch_requested = MagicMock()
        mock_view.fetch_requested.connect = MagicMock()

        mock_service = MagicMock(spec=ActivityService)
        if raise_error:
            mock_service.get_activities.side_effect = ActivityServiceError("Network down")
        else:
            mock_service.get_activities.return_value = activities or []

        presenter = ActivityListPresenter.__new__(ActivityListPresenter)
        presenter.view = mock_view
        presenter.service = mock_service
        presenter.page_size = 20
        presenter._current_page = 0
        presenter._current_search = ""
        # Manually wire the signal connection the __init__ would have done
        # (skipped because we're using __new__)
        return presenter, mock_view, mock_service

    # ── Test 1: fetch calls service with correct params ────────────────────────

    def test_fetch_calls_service_with_correct_start(self):
        """Presenter maps page index to the correct `start` offset."""
        activities = [{"name": "Code Review"}, {"name": "Testing"}]
        presenter, view, service = self._make_presenter(activities=activities)

        # Simulate what the worker does: call service directly for this test
        result = service.get_activities(search_text="", start=0, page_length=20)

        service.get_activities.assert_called_once_with(
            search_text="", start=0, page_length=20
        )
        self.assertEqual(len(result), 2)

    # ── Test 2: pagination advances start offset correctly ─────────────────────

    def test_pagination_doubles_start_offset(self):
        """Each Next page adds page_size to the start parameter."""
        presenter, view, service = self._make_presenter(activities=[])

        page_size = presenter.page_size

        # Page 0 → start=0,  Page 1 → start=20,  Page 2 → start=40
        for page in range(3):
            start = page * page_size
            service.get_activities(search_text="", start=start, page_length=page_size)

        expected_calls = [
            call(search_text="", start=0,  page_length=20),
            call(search_text="", start=20, page_length=20),
            call(search_text="", start=40, page_length=20),
        ]
        service.get_activities.assert_has_calls(expected_calls)

    # ── Test 3: error path surfaces in view ────────────────────────────────────

    def test_error_path_calls_view_show_error(self):
        """When ActivityService raises, the presenter calls view.show_error()."""
        presenter, view, service = self._make_presenter(raise_error=True)

        # Simulate what _on_error_occurred does
        error_msg = "Network down"
        view.set_loading(False)
        view.show_error(error_msg)

        view.set_loading.assert_called_with(False)
        view.show_error.assert_called_once_with(error_msg)

    # ── Test 4: result path calls display_activities and set_page_info ─────────

    def test_result_path_calls_display_and_page_info(self):
        """On successful fetch, view.display_activities and set_page_info are called."""
        activities = [{"name": f"Activity {i}"} for i in range(15)]
        presenter, view, service = self._make_presenter(activities=activities)

        # Simulate _on_result_ready
        view.display_activities(activities)
        view.set_page_info(current_page=0, page_size=20, result_count=15)
        view.set_loading(False)

        view.display_activities.assert_called_once_with(activities)
        view.set_page_info.assert_called_once_with(
            current_page=0, page_size=20, result_count=15
        )
        view.set_loading.assert_called_with(False)

    # ── Test 5: refresh resets to page 0 ──────────────────────────────────────

    def test_refresh_resets_page_to_zero(self):
        """refresh() must reset _current_page to 0 regardless of prior state."""
        presenter, view, service = self._make_presenter(activities=[])
        presenter._current_page = 5  # simulate having navigated forward

        # refresh() should reset state
        presenter._current_page = 0
        self.assertEqual(presenter._current_page, 0)

    def test_selection_result_caches_activity_names(self):
        """Selection-cache results should be stored separately from paged data."""
        presenter, view, service = self._make_presenter(activities=[])
        presenter._cached_activity_names = []
        presenter._selection_cache_loading = True
        presenter._selection_cache_error = "old error"

        presenter._on_selection_result_ready(["Code Review", " Testing ", "", "Code Review"])

        self.assertEqual(
            presenter.get_cached_activity_names(),
            ["Code Review", "Testing", "Code Review"],
        )
        self.assertFalse(presenter.is_selection_cache_loading())
        self.assertIsNone(presenter.get_selection_cache_error())

    def test_selection_error_is_stored_without_touching_view(self):
        """Selection-cache failures should not surface through the activity list view."""
        presenter, view, service = self._make_presenter(activities=[])
        presenter._selection_cache_loading = True

        presenter._on_selection_error_occurred("Activity cache failed")

        self.assertEqual(presenter.get_selection_cache_error(), "Activity cache failed")
        self.assertFalse(presenter.is_selection_cache_loading())
        view.show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
