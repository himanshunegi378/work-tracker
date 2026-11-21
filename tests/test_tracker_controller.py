import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtWidgets import QApplication

from src.core import prefs
from src.ui.tracker_controller import JOB_NAME, TrackerController


class FakeScheduler:
    def __init__(self):
        self.active = False
        self.jobs = []
        self.stops = 0

    def add_job(self, name, task_func, interval_seconds, invoke_on_start=False):
        self.jobs.append({"name": name, "interval": interval_seconds, "fn": task_func, "now": invoke_on_start})

    def start(self):
        self.active = True

    def stop(self):
        self.active = False
        self.jobs.clear()
        self.stops += 1

    def is_active(self):
        return self.active

    def seconds_until_next(self, name):
        return 42.4 if self.active and self.jobs and self.jobs[0]["name"] == name else None


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")

    def build():
        scheduler = FakeScheduler()
        return TrackerController(scheduler=scheduler), scheduler

    return build


def test_start_uses_the_saved_interval_and_prompts_immediately(make):
    prefs.set_value("interval", "20m")
    tracker, sched = make()
    states = []
    tracker.state_changed.connect(states.append)
    status = tracker.start()
    assert status == {"active": True, "interval_seconds": 1200, "next_prompt_in_seconds": 42}
    assert sched.jobs[0]["name"] == JOB_NAME and sched.jobs[0]["now"] is True
    assert tracker.initial_prompt is True and states == [True]


def test_start_with_an_explicit_interval_overrides_the_setting(make):
    tracker, _ = make()
    assert tracker.start(300)["interval_seconds"] == 300
    assert prefs.get_interval_seconds() == 900  # the saved preference is untouched


@pytest.mark.parametrize("seconds", [0, 59, 86401])
def test_start_rejects_out_of_range_intervals(make, seconds):
    tracker, sched = make()
    with pytest.raises(ValueError, match="between 1m and 24h"):
        tracker.start(seconds)
    assert not sched.active


def test_starting_again_with_the_same_interval_does_nothing(make):
    tracker, sched = make()
    states = []
    tracker.state_changed.connect(states.append)
    tracker.start(600)
    tracker.start(600)
    assert len(sched.jobs) == 1 and sched.stops == 0 and states == [True]


def test_starting_with_a_new_interval_restarts(make):
    tracker, sched = make()
    tracker.start(600)
    assert tracker.start(1200)["interval_seconds"] == 1200
    assert sched.stops == 1 and len(sched.jobs) == 1 and sched.jobs[0]["interval"] == 1200


def test_stop_reports_state_and_clears_the_initial_flag(make):
    tracker, sched = make()
    states = []
    tracker.state_changed.connect(states.append)
    tracker.start()
    assert tracker.stop()["active"] is False
    assert tracker.initial_prompt is False and states == [True, False]


def test_stopping_an_idle_tracker_is_quiet_and_does_not_touch_the_scheduler(make):
    tracker, sched = make()
    states = []
    tracker.state_changed.connect(states.append)
    assert tracker.stop() == {"active": False, "interval_seconds": 900, "next_prompt_in_seconds": None}
    assert sched.stops == 0 and states == []


def test_the_scheduled_job_emits_prompt_requested(make):
    tracker, sched = make()
    fired = []
    tracker.prompt_requested.connect(lambda: fired.append(1))
    tracker.start()
    sched.jobs[0]["fn"]()
    assert fired == [1]
