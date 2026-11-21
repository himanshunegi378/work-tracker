"""Owns the reminder scheduler so the dashboard, tray icon and CLI all drive one tracker."""

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

from src.core import prefs
from src.services.scheduler import CronScheduler

logger = logging.getLogger(__name__)

JOB_NAME = "Smart Log Prompt"
MIN_INTERVAL = prefs.MIN_INTERVAL_SECONDS
MAX_INTERVAL = prefs.MAX_INTERVAL_SECONDS


class TrackerController(QObject):
    """Start/stop periodic log reminders.

    `prompt_requested` is emitted from the scheduler thread; Qt delivers it to
    listeners on the GUI thread, which is where the dialog must be opened.
    """

    prompt_requested = Signal()
    state_changed = Signal(bool)  # True when the tracker becomes active

    def __init__(self, scheduler: Optional[CronScheduler] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._scheduler = scheduler or CronScheduler(tick_interval=5.0)
        self.interval_seconds: int = prefs.get_interval_seconds()
        self.initial_prompt = False  # first prompt after start logs a zero-length placeholder

    @property
    def active(self) -> bool:
        return self._scheduler.is_active()

    def start(self, interval_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Start (or restart with a new interval). Returns the new status."""
        if interval_seconds is not None and not MIN_INTERVAL <= interval_seconds <= MAX_INTERVAL:
            raise ValueError("Interval must be between 1m and 24h.")
        wanted = interval_seconds or prefs.get_interval_seconds()
        if self.active:
            if wanted == self.interval_seconds:
                return self.status()
            self._scheduler.stop()  # restart with the new interval

        self.interval_seconds = wanted
        self.initial_prompt = True
        self._scheduler.add_job(
            name=JOB_NAME,
            task_func=self.prompt_requested.emit,
            interval_seconds=self.interval_seconds,
            invoke_on_start=True,  # the first prompt appears immediately
        )
        self._scheduler.start()
        logger.info("Tracker started, reminding every %ss", self.interval_seconds)
        self.state_changed.emit(True)
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self.initial_prompt = False
        if self.active:
            self._scheduler.stop()
            logger.info("Tracker stopped")
            self.state_changed.emit(False)
        return self.status()

    def status(self) -> Dict[str, Any]:
        remaining = self._scheduler.seconds_until_next(JOB_NAME) if self.active else None
        return {
            "active": self.active,
            "interval_seconds": self.interval_seconds,
            "next_prompt_in_seconds": round(remaining) if remaining is not None else None,
        }
