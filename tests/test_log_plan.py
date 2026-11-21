import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.dates import parse_time
from src.core.log_plan import PlanError, plan_log

NOW = datetime(2026, 11, 21, 15, 0, 0)
BASE = dict(project_id="PROJ-1", activity="Development", description="work", is_billable=False, now=NOW)


def prev(end="2026-11-21 14:00:00", **over):
    state = {"timesheet_name": "TS-1", "project_id": "PROJ-1", "activity_name": "Development",
             "description": "old", "is_billable": False, "timestamp": end}
    state.update(over)
    return state


def test_no_previous_entry_uses_default_interval_ending_now():
    plan = plan_log(previous_state=None, default_interval_seconds=900, **BASE)
    assert (plan.from_dt, plan.to_dt) == (datetime(2026, 11, 21, 14, 45), NOW)
    assert plan.hours == 0.25 and not plan.merges and plan.timesheet_name is None


def test_no_previous_entry_with_duration():
    plan = plan_log(previous_state=None, duration_seconds=5400, **BASE)
    assert plan.from_dt == datetime(2026, 11, 21, 13, 30) and plan.hours == 1.5


def test_same_day_previous_without_duration_runs_from_previous_end_to_now():
    plan = plan_log(previous_state=prev(), **BASE)
    assert plan.from_dt == datetime(2026, 11, 21, 14, 0, 1) and plan.to_dt == NOW
    assert plan.timesheet_name == "TS-1"


def test_same_day_previous_with_duration_starts_after_previous_and_runs_that_long():
    plan = plan_log(previous_state=prev(end="2026-11-21 13:00:00"), duration_seconds=3600, **BASE)
    assert plan.from_dt == datetime(2026, 11, 21, 13, 0, 1)
    assert plan.to_dt == datetime(2026, 11, 21, 14, 0, 1)
    assert abs(plan.hours - 1.0) < 0.001 and plan.notes == []


def test_previous_on_another_day_is_ignored_for_the_window():
    plan = plan_log(previous_state=prev(end="2026-11-20 17:00:00"), duration_seconds=3600, **BASE)
    assert (plan.from_dt, plan.to_dt) == (datetime(2026, 11, 21, 14, 0), NOW)
    assert plan.timesheet_name is None


def test_identical_entry_merges_and_extends_previous():
    plan = plan_log(previous_state=prev(description="work"), duration_seconds=1800, **BASE)
    assert plan.merges and plan.to_dt == datetime(2026, 11, 21, 14, 30)
    assert plan.hours == 0.5 and "extended" in plan.notes[0]


def test_different_billing_does_not_merge():
    plan = plan_log(previous_state=prev(description="work", is_billable=True), **BASE)
    assert not plan.merges


def test_end_at_with_duration_for_a_past_day():
    plan = plan_log(
        previous_state=None, duration_seconds=7200, end_at=datetime(2026, 11, 18, 17, 0), **BASE
    )
    assert plan.from_dt == datetime(2026, 11, 18, 15, 0) and plan.to_dt == datetime(2026, 11, 18, 17, 0)
    assert plan.saved_at == datetime(2026, 11, 18, 17, 0) and plan.interval_seconds == 7200


def test_end_at_after_same_day_previous_warns_when_length_differs():
    plan = plan_log(
        previous_state=prev(end="2026-11-21 10:00:00"), duration_seconds=3600,
        end_at=datetime(2026, 11, 21, 14, 0), **BASE,
    )
    assert plan.hours > 3.9
    assert "not 1h" in plan.notes[0] and "10:00" in plan.notes[0]


def test_end_at_requires_duration():
    with pytest.raises(PlanError, match="--at needs --duration"):
        plan_log(previous_state=None, end_at=datetime(2026, 11, 21, 9, 0), **BASE)


def test_future_end_is_rejected():
    with pytest.raises(PlanError, match="future"):
        plan_log(previous_state=prev(end="2026-11-21 14:30:00"), duration_seconds=3 * 3600, **BASE)
    with pytest.raises(PlanError, match="future"):
        plan_log(previous_state=None, duration_seconds=3600, end_at=datetime(2026, 11, 21, 18, 0), **BASE)


def test_end_before_previous_end_is_rejected():
    with pytest.raises(PlanError, match="before your previous entry"):
        plan_log(previous_state=prev(end="2026-11-21 14:00:00"), duration_seconds=600,
                 end_at=datetime(2026, 11, 21, 13, 0), **BASE)


@pytest.mark.parametrize("seconds", [0, 30, 25 * 3600])
def test_duration_limits(seconds):
    with pytest.raises(PlanError, match="between 1m and 24h"):
        plan_log(previous_state=None, duration_seconds=seconds, **BASE)


@pytest.mark.parametrize("text,hm", [("14:30", (14, 30)), ("9:05", (9, 5)), ("9am", (9, 0)), ("12am", (0, 0)),
                                     ("12pm", (12, 0)), ("2:30 pm", (14, 30)), ("17", (17, 0))])
def test_parse_time(text, hm):
    t = parse_time(text)
    assert (t.hour, t.minute) == hm


@pytest.mark.parametrize("bad", ["", "25:00", "9:60", "13pm", "0am", "noon", "9:5"])
def test_parse_time_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


def test_parse_time_now():
    assert parse_time("now", now=datetime(2026, 1, 1, 8, 7, 59)).minute == 7


def test_duration_text_rounds_to_the_nearest_minute_but_keeps_exact_hours():
    plan = plan_log(previous_state=prev(end="2026-11-21 13:00:04.5"), duration_seconds=3600,
                    end_at=datetime(2026, 11, 21, 14, 0, 0), **BASE)
    assert plan.duration_text == "1h"
    assert plan.hours != 1.0  # 13:00:05 to 14:00:00 is 59m55s; only the display is rounded
