"""Regression: rapid screen refreshes against the real thread pool must not crash Qt.

Connecting a worker's signals to bare closures (no QObject receiver) let Qt deliver a queued
result to a destroyed object: a segfault that only shows up with real threads and uneven
latency, so this runs in a subprocess and checks the exit code. (Verified: the old closure
pattern crashes this scenario every time; run_in_background survives it.)
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = textwrap.dedent(
    """
    import os, random, sys, time
    random.seed(5)
    sys.path.insert(0, {root!r})
    from unittest.mock import MagicMock
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from src.ui.leave_list_presenter import LeaveListPresenter
    from src.ui.views.leave_list_view import LeaveListView

    def lag(value):  # jittered latency like a real network call; fixed delays don't trigger the race
        def call(*args, **kwargs):
            time.sleep(random.uniform(0.0, 0.05))
            return value
        return call

    service = MagicMock()
    service.get_leave_applications.side_effect = lag([])
    service.get_leave_balance.side_effect = lag(
        [{{"leave_type": "Sick Leave", "total_leaves": 6.0, "leaves_taken": 5.0, "remaining_leaves": 1.0}}])
    service.get_leave_types.side_effect = lag(["Sick Leave"])
    employees = MagicMock()
    employees.get_employees.side_effect = lag([{{"employee": "a", "employee_name": "A"}}])

    view = LeaveListView()
    view.show()
    presenter = LeaveListPresenter(view, service, employee_service=employees)
    for i in range(200):
        presenter.refresh()
        view.employee_combo.setCurrentIndex(i % 3)
        pump_until = time.time() + 0.01
        while time.time() < pump_until:
            app.processEvents()
            time.sleep(0.001)
    end = time.time() + 1.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    print("SURVIVED")
    """
)


def test_rapid_leave_refreshes_do_not_crash_the_event_loop():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", SCRIPT.format(root=str(ROOT))],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert result.returncode == 0 and "SURVIVED" in result.stdout, (
        f"exit={result.returncode}\n{result.stderr[-1500:]}"
    )
