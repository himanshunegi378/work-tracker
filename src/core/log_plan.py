"""Work out exactly what `log add` will save, before saving it.

Mirrors the rules in services/timesheet_smart_log.py so the preview matches the
result: a new entry starts one second after your previous entry on the same day
and ends at the chosen time; an entry identical to the previous one extends it.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.durations import format_duration
from src.services.timesheet_smart_log import (
    coerce_optional_datetime,
    coerce_to_strictly_later_second,
    compute_hours,
    resolve_new_time_log_window,
)

MIN_DURATION_SECONDS = 60
MAX_DURATION_SECONDS = 24 * 3600
_FUTURE_GRACE = timedelta(minutes=1)


class PlanError(ValueError):
    """The requested log can't be saved as asked (message is user-facing)."""


@dataclass
class LogPlan:
    from_dt: datetime
    to_dt: datetime
    hours: float
    saved_at: datetime          # passed to save_timesheet_log
    interval_seconds: int       # passed to save_timesheet_log
    merges: bool                # extends the previous entry instead of adding a row
    timesheet_name: Optional[str]  # known only when the day's timesheet already exists
    notes: List[str] = field(default_factory=list)

    @property
    def duration_text(self) -> str:
        """Length for display: nearest minute (stored hours stay exact)."""
        seconds = round(self.hours * 3600)
        return format_duration(round(seconds / 60) * 60 if seconds >= 60 else seconds)


def _clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def plan_log(
    *,
    previous_state: Optional[Dict[str, Any]],
    project_id: str,
    activity: str,
    description: str,
    is_billable: bool,
    now: datetime,
    duration_seconds: Optional[int] = None,
    default_interval_seconds: int = 15 * 60,
    end_at: Optional[datetime] = None,
) -> LogPlan:
    if duration_seconds is not None and not MIN_DURATION_SECONDS <= duration_seconds <= MAX_DURATION_SECONDS:
        raise PlanError("Duration must be between 1m and 24h.")
    if end_at is not None and duration_seconds is None:
        raise PlanError("--at needs --duration (the entry's length).")

    now = now.replace(microsecond=0)
    target_day = (end_at or now).date()
    prev_end = coerce_optional_datetime(previous_state.get("timestamp")) if previous_state else None
    same_day = prev_end is not None and prev_end.date() == target_day
    merges = bool(
        same_day
        and previous_state.get("project_id") == project_id
        and previous_state.get("activity_name") == activity
        and previous_state.get("description") == description
        and bool(previous_state.get("is_billable")) == is_billable
    )

    if end_at is not None:
        end_dt, interval = end_at.replace(microsecond=0), duration_seconds
    elif duration_seconds is not None and same_day:
        # start right after the previous entry and run for the requested time
        base = prev_end if merges else coerce_to_strictly_later_second(prev_end)
        end_dt, interval = base + timedelta(seconds=duration_seconds), duration_seconds
    else:
        end_dt = now
        interval = duration_seconds or default_interval_seconds

    if end_dt > now + _FUTURE_GRACE:
        raise PlanError(
            f"That entry would end in the future ({end_dt:%Y-%m-%d %H:%M}). "
            "Use a shorter --duration or an earlier --at."
        )
    if same_day and end_dt < prev_end:
        raise PlanError(
            f"That ends at {_clock(end_dt)}, before your previous entry ends ({_clock(prev_end)}). "
            "Pick a later --at."
        )

    if merges:
        from_dt, to_dt, hours = prev_end, end_dt, compute_hours(prev_end, end_dt)
    else:
        from_dt, to_dt, hours = resolve_new_time_log_window(
            previous_dt=prev_end,
            current_dt=end_dt,
            interval_seconds=interval,
            interval_hours=round(interval / 3600, 6),
        )

    plan = LogPlan(
        from_dt=from_dt, to_dt=to_dt, hours=hours, saved_at=end_dt, interval_seconds=interval,
        merges=merges, timesheet_name=previous_state.get("timesheet_name") if same_day else None,
    )

    if merges:
        plan.notes.append(
            f"Same project, activity, description and billing as your previous entry, so it is "
            f"extended to {_clock(end_dt)} (+{plan.duration_text}) instead of adding a row."
        )
    if duration_seconds is not None and abs(hours * 3600 - duration_seconds) > 60:
        plan.notes.append(
            f"Your previous entry ends at {_clock(prev_end)}, so this logs {plan.duration_text} "
            f"({_clock(from_dt)}-{_clock(to_dt)}), not {format_duration(duration_seconds)}."
        )
    return plan
