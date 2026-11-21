import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from src.ui.timesheet_detail_presenter import TimesheetDetailPresenter
from src.ui.timesheet_module_presenter import TimesheetModulePresenter
from src.ui.views.edit_entry_dialog import EditEntryDialog
from src.ui.views.timesheet_detail_view import TimesheetDetailView
from src.ui.views.timesheet_module_view import TimesheetModuleView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def detail(state="Pending"):
    return {
        "name": "TS-9", "workflow_state": state, "status": "Draft", "start_date": "2026-11-21", "end_date": "2026-11-21",
        "total_hours": 3.0, "total_billable_hours": 0.0,
        "time_logs": [
            {"name": "r1", "idx": 1, "activity_type": "Execution", "project": "PROJ-7", "project_name": "TATVA",
             "description": "first", "from_time": "2026-11-21 09:00:00", "to_time": "2026-11-21 10:00:00",
             "hours": 1.0, "is_billable": 0},
            {"name": "r2", "idx": 2, "activity_type": "Review", "project": "PROJ-1", "project_name": "Billing",
             "description": "second", "from_time": "2026-11-21 10:00:01", "to_time": "2026-11-21 12:00:00",
             "hours": 2.0, "is_billable": 1},
        ],
    }


@pytest.fixture
def view(qapp):
    v = TimesheetDetailView()
    v.display_timesheet_detail(detail())
    return v


# ── view ──────────────────────────────────────────────────────────────────
def test_buttons_follow_the_selection_for_a_pending_timesheet(view):
    assert view.is_editable
    assert not view.edit_btn.isEnabled() and not view.delete_entry_btn.isEnabled()
    assert view.submit_btn.isEnabled() and view.delete_timesheet_btn.isEnabled()
    view.time_logs_table.selectRow(1)
    assert view.edit_btn.isEnabled() and view.delete_entry_btn.isEnabled()
    assert view.selected_entry_name() == "r2"


@pytest.mark.parametrize("state", ["Submitted", "Approved", "Rejected"])
def test_everything_is_disabled_for_a_timesheet_that_is_not_pending(qapp, state):
    v = TimesheetDetailView()
    v.display_timesheet_detail(detail(state))
    v.time_logs_table.selectRow(0)
    assert not v.is_editable
    assert not any(b.isEnabled() for b in (v.edit_btn, v.delete_entry_btn, v.submit_btn, v.delete_timesheet_btn))
    assert "Only Pending" in v.actions_note.text()


def test_an_empty_pending_timesheet_cannot_be_submitted(qapp):
    v = TimesheetDetailView()
    d = detail()
    d["time_logs"] = []
    v.display_timesheet_detail(d)
    assert v.delete_timesheet_btn.isEnabled() and not v.submit_btn.isEnabled()


def test_buttons_emit_the_selected_entry_and_timesheet_actions(view):
    seen = []
    view.edit_entry_requested.connect(lambda n: seen.append(("edit", n)))
    view.delete_entry_requested.connect(lambda n: seen.append(("delete", n)))
    view.submit_requested.connect(lambda: seen.append("submit"))
    view.delete_timesheet_requested.connect(lambda: seen.append("rm"))
    view.time_logs_table.selectRow(0)
    for button in (view.edit_btn, view.delete_entry_btn, view.submit_btn, view.delete_timesheet_btn):
        button.click()
    assert seen == [("edit", "r1"), ("delete", "r1"), "submit", "rm"]


def test_loading_disables_the_actions_and_finishing_restores_them(view):
    view.set_loading(True)
    assert not view.submit_btn.isEnabled()
    view.display_timesheet_detail(detail())
    view.set_loading(False)
    assert view.submit_btn.isEnabled()


# ── presenter ─────────────────────────────────────────────────────────────
class Harness:
    def __init__(self, view, answer=True):
        self.service = MagicMock()
        self.projects = MagicMock()
        self.projects.get_projects.return_value = [{"id": "PROJ-7", "name": "TATVA"}, {"id": "PROJ-1", "name": "Billing"}]
        self.activities = MagicMock()
        self.activities.get_activity_names.return_value = ["Execution", "Review"]
        self.view = view
        self.errors = []
        self.asked = []
        view.confirm = lambda title, text: self.asked.append(title) or answer
        view.show_error_titled = lambda title, message: self.errors.append((title, message))
        self.presenter = TimesheetDetailPresenter(view, self.service, self.projects, self.activities)
        self.presenter._current_name = "TS-9"
        self.fetches = []
        self.presenter._fetch = self.fetches.append
        self.events = []
        self.presenter.data_changed.connect(lambda: self.events.append("changed"))
        self.presenter.timesheet_deleted.connect(lambda: self.events.append("deleted"))

        def run(fn, on_done, title):  # run synchronously instead of on a thread
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                self.presenter._failed(title, str(exc))
            else:
                on_done(result)

        self.presenter._run = run


@pytest.fixture
def harness(view):
    return Harness(view)


def test_delete_entry_asks_then_deletes_and_reloads(harness):
    harness.presenter.delete_entry("r2")
    assert harness.asked == ["Delete entry"]
    harness.service.delete_time_log.assert_called_once_with("TS-9", "r2")
    assert harness.events == ["changed"] and harness.fetches == ["TS-9"]


def test_declining_the_confirmation_changes_nothing(view):
    h = Harness(view, answer=False)
    for action in (lambda: h.presenter.delete_entry("r1"), h.presenter.submit_timesheet, h.presenter.delete_timesheet):
        action()
    assert h.service.mock_calls == [] and h.events == [] and h.fetches == []


def test_submit_asks_with_a_warning_and_submits(harness):
    harness.presenter.submit_timesheet()
    harness.service.submit_timesheet.assert_called_once_with("TS-9")
    assert harness.asked == ["Submit timesheet"] and harness.events == ["changed"]


def test_delete_timesheet_signals_so_the_module_can_return_to_the_list(harness):
    harness.presenter.delete_timesheet()
    harness.service.delete_timesheet.assert_called_once_with("TS-9")
    assert harness.events == ["changed", "deleted"] and harness.fetches == []


def test_service_errors_are_shown_and_nothing_is_reloaded_as_success(harness):
    harness.service.delete_time_log.side_effect = RuntimeError("That is the only entry")
    harness.presenter.delete_entry("r1")
    assert harness.errors == [("Could not delete the entry", "That is the only entry")]
    assert harness.events == []


def test_apply_changes_saves_only_what_changed(harness):
    harness.presenter.apply_entry_changes("r1", {"description": "new"})
    harness.service.update_time_log.assert_called_once_with("TS-9", "r1", description="new")
    assert harness.events == ["changed"]


def test_apply_with_no_changes_just_reloads(harness):
    harness.presenter.apply_entry_changes("r1", {})
    harness.service.update_time_log.assert_not_called()
    assert harness.events == [] and harness.fetches == ["TS-9"]


def test_edit_loads_projects_and_activities_then_opens_the_dialog(harness, monkeypatch):
    shown = {}

    class FakeDialog:
        def __init__(self, entry, projects, activities, parent=None):
            shown.update(entry=entry, projects=projects, activities=activities)

        def exec(self):
            return True

        def get_changes(self):
            return {"is_billable": True}

    monkeypatch.setattr("src.ui.timesheet_detail_presenter.EditEntryDialog", FakeDialog)
    harness.presenter.edit_entry("r1")
    assert shown["entry"]["name"] == "r1" and [p["id"] for p in shown["projects"]] == ["PROJ-7", "PROJ-1"]
    assert shown["activities"] == ["Execution", "Review"]
    harness.service.update_time_log.assert_called_once_with("TS-9", "r1", is_billable=True)


def test_cancelling_the_edit_dialog_changes_nothing(harness, monkeypatch):
    class Cancelled:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return False

    monkeypatch.setattr("src.ui.timesheet_detail_presenter.EditEntryDialog", Cancelled)
    harness.presenter.edit_entry("r1")
    harness.service.update_time_log.assert_not_called()


def test_edit_without_project_and_activity_services_explains_itself(view):
    h = Harness(view)
    h.presenter.project_service = None
    h.presenter.edit_entry("r1")
    assert h.errors and "not available" in h.errors[0][1]


def test_module_presenter_returns_to_the_list_after_a_delete_and_forwards_changes(qapp):
    module_view = TimesheetModuleView()
    service = MagicMock()
    service.get_timesheets.return_value = []
    module = TimesheetModulePresenter(module_view, service, project_service=MagicMock(), activity_service=MagicMock())
    module.list_presenter.refresh = MagicMock()
    changed = []
    module.data_changed.connect(lambda: changed.append(1))
    module_view.show_detail()
    module.detail_presenter.timesheet_deleted.emit()
    assert module_view.stack.currentWidget() is module_view.list_view
    module.list_presenter.refresh.assert_called_once()
    module.detail_presenter.data_changed.emit()
    assert changed == [1]


# ── edit dialog ───────────────────────────────────────────────────────────
PROJECTS = [{"id": "PROJ-7", "name": "TATVA"}, {"id": "PROJ-1", "name": "Billing"}]


def make_dialog(qapp):
    return EditEntryDialog(detail()["time_logs"][0], PROJECTS, ["Execution", "Review"])


def test_dialog_starts_on_the_entrys_values_and_reports_no_changes(qapp):
    d = make_dialog(qapp)
    assert d.project_combo.currentData() == ("PROJ-7", "TATVA") and d.activity_combo.currentText() == "Execution"
    assert d.description_input.text() == "first" and not d.billable_check.isChecked()
    assert d.get_changes() == {}


def test_dialog_reports_only_changed_fields(qapp):
    d = make_dialog(qapp)
    d.description_input.setText("  reworded ")
    d.activity_combo.setCurrentText("Review")
    d.project_combo.setCurrentIndex(1)
    d.billable_check.setChecked(True)
    d.to_edit.setTime(d.to_edit.time().fromString("09:30", "HH:mm"))
    assert d.get_changes() == {
        "description": "reworded", "activity": "Review", "project_id": "PROJ-1", "project_name": "Billing",
        "is_billable": True, "to_time": datetime(2026, 11, 21, 9, 30),
    }


def test_dialog_validation(qapp):
    d = make_dialog(qapp)
    d.description_input.setText("   ")
    assert "Description" in d.validate()
    d.description_input.setText("ok")
    d.to_edit.setTime(d.from_edit.time())
    assert "end time" in d.validate()
    d._on_save()
    assert not d.error.isHidden() and d.result() != QDialog.Accepted


def test_dialog_keeps_a_project_or_activity_that_is_not_in_the_lists(qapp):
    entry = dict(detail()["time_logs"][0], project="PROJ-X", project_name="Old", activity_type="Legacy")
    d = EditEntryDialog(entry, PROJECTS, ["Execution"])
    assert d.project_combo.currentData() == ("PROJ-X", "Old") and d.activity_combo.currentText() == "Legacy"
    assert d.get_changes() == {}


# ── threading: callbacks must run on the GUI thread ───────────────────────
def _pump(qapp, predicate, seconds=3):
    import time

    from PySide6.QtCore import QThreadPool

    end = time.time() + seconds
    while not predicate() and time.time() < end:
        qapp.processEvents()
        QThreadPool.globalInstance().waitForDone(20)
        time.sleep(0.01)
    qapp.processEvents()


def test_worker_callbacks_run_on_the_gui_thread_not_the_worker_thread(qapp, view):
    import threading

    presenter = TimesheetDetailPresenter(view, MagicMock())
    seen = {}
    worker_thread = {}

    def work():
        worker_thread["id"] = threading.get_ident()
        return "result"

    presenter._run(work, lambda result: seen.update(done=threading.get_ident(), result=result), "failed")
    _pump(qapp, lambda: "done" in seen)
    assert seen["result"] == "result"
    assert seen["done"] == threading.get_ident() != worker_thread["id"]


def test_error_callbacks_also_run_on_the_gui_thread(qapp, view):
    import threading

    presenter = TimesheetDetailPresenter(view, MagicMock())
    errors = []
    view.show_error_titled = lambda title, message: errors.append((title, message, threading.get_ident()))

    def boom():
        raise RuntimeError("nope")

    presenter._run(boom, lambda r: None, "Could not do it")
    _pump(qapp, lambda: errors)
    assert errors[0][:2] == ("Could not do it", "nope") and errors[0][2] == threading.get_ident()
