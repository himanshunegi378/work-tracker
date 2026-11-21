import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli import gui_launcher
from src.cli.app import app
from src.cli.commands import tracker as tracker_cmd
from src.cli.errors import CliError
from src.core import ipc, prefs

runner = CliRunner()


def status_payload(active=False, **over):
    data = {
        "pid": 1, "tracker": {"active": active, "interval_seconds": 900,
                              "next_prompt_in_seconds": 540 if active else None},
        "window_visible": False, "tray": True, "started_hidden": True, "window_shown": False,
    }
    data.update(over)
    return data


class FakeApp:
    """Stands in for the desktop app: records requests, answers like the real one."""

    def __init__(self, running=True, **status_over):
        self.running = running
        self.requests = []
        self.state = status_payload(**status_over)

    def request(self, cmd, args=None, timeout=3.0):
        if not self.running:
            raise ipc.IpcUnavailable("The desktop app is not running.")
        self.requests.append((cmd, args or {}))
        if cmd == "tracker.start":
            self.state["tracker"].update(active=True, interval_seconds=(args or {}).get("every") or 900,
                                         next_prompt_in_seconds=(args or {}).get("every") or 900)
        if cmd == "tracker.stop":
            self.state["tracker"].update(active=False, next_prompt_in_seconds=None)
        if cmd == "app.quit":
            self.running = False
        return self.state if cmd.startswith("tracker") else {}

    def is_running(self):
        return self.running

    def commands(self):
        return [c for c, _ in self.requests]


@pytest.fixture
def desktop(monkeypatch):
    fake = FakeApp()
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    monkeypatch.setattr(gui_launcher, "wait_until_stopped", lambda timeout=5.0: True)
    return fake


def run(*args, **kw):
    return runner.invoke(app, list(args), **kw)


# ── start ─────────────────────────────────────────────────────────────────
def test_start_when_the_app_is_running_just_starts_the_tracker(desktop, monkeypatch):
    launched = []
    monkeypatch.setattr(gui_launcher, "launch_gui", lambda hidden: launched.append(hidden))
    result = run("start", "--every", "10m")
    assert result.exit_code == 0 and "reminders every 10m" in result.output
    assert desktop.requests == [("tracker.start", {"every": 600})] and launched == []


def test_start_without_every_uses_the_apps_setting(desktop):
    run("start")
    assert desktop.requests == [("tracker.start", {})]


def test_start_launches_the_app_hidden_when_it_is_not_running(monkeypatch):
    fake = FakeApp(running=False)
    launches = []

    def launch(hidden):
        launches.append(hidden)
        fake.running = True
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    monkeypatch.setattr(gui_launcher, "display_available", lambda: True)
    monkeypatch.setattr(gui_launcher, "launch_gui", launch)
    result = run("start")
    assert result.exit_code == 0 and launches == [True] and "in the tray" in result.output
    assert fake.commands() == ["tracker.start"]


def test_start_show_launches_visible_or_raises_the_window(monkeypatch, desktop):
    run("start", "--show")
    assert desktop.commands() == ["window.show", "tracker.start"]


def test_start_without_a_display_exits_4_and_suggests_remind(monkeypatch):
    fake = FakeApp(running=False)
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    monkeypatch.setattr(gui_launcher, "display_available", lambda: False)
    result = run("start")
    assert result.exit_code == 4 and "samta-tracker remind" in result.output


def test_start_reports_an_app_that_dies_while_starting(monkeypatch):
    fake = FakeApp(running=False)
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    monkeypatch.setattr(gui_launcher, "display_available", lambda: True)
    monkeypatch.setattr(gui_launcher, "launch_gui", lambda hidden: SimpleNamespace(poll=lambda: 3, returncode=3))
    result = run("start")
    assert result.exit_code == 1 and "exited right after starting" in result.output


@pytest.mark.parametrize("bad", ["abc", "10s", "48h"])
def test_start_rejects_bad_intervals(desktop, bad):
    assert run("start", "--every", bad).exit_code == 2
    assert desktop.requests == []


def test_start_json(desktop):
    out = json.loads(run("--json", "start", "--every", "5m").output)
    assert out["launched_app"] is False and out["tracker"]["interval_seconds"] == 300


# ── stop ──────────────────────────────────────────────────────────────────
def test_stop_when_not_running_is_a_quiet_success(monkeypatch):
    monkeypatch.setattr(ipc, "is_running", lambda: False)
    result = run("stop")
    assert result.exit_code == 0 and "isn't running" in result.output


def test_stop_closes_an_app_the_cli_started_and_nobody_opened(desktop):
    result = run("stop")
    assert desktop.commands() == ["tracker.stop", "app.quit"]
    assert "desktop app closed" in result.output


def test_stop_keeps_an_app_the_user_has_opened(monkeypatch):
    fake = FakeApp(window_shown=True)
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    result = run("stop")
    assert fake.commands() == ["tracker.stop"] and "closed" not in result.output


def test_stop_keeps_an_app_that_was_started_normally(monkeypatch):
    fake = FakeApp(started_hidden=False)
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    run("stop")
    assert fake.commands() == ["tracker.stop"]


def test_stop_quit_always_closes(monkeypatch):
    fake = FakeApp(window_shown=True, started_hidden=False)
    monkeypatch.setattr(ipc, "request", fake.request)
    monkeypatch.setattr(ipc, "is_running", fake.is_running)
    monkeypatch.setattr(gui_launcher, "wait_until_stopped", lambda timeout=5.0: True)
    run("stop", "--quit")
    assert fake.commands() == ["tracker.stop", "app.quit"]


# ── status ────────────────────────────────────────────────────────────────
class FakeAuth:
    def __init__(self, user="jane@samta.ai"):
        self.user = user

    def getSession(self):
        return self.user

    def get_saved_username(self):
        return None

    def get_saved_password(self):
        return None


@pytest.fixture
def services(monkeypatch):
    ctx = SimpleNamespace(
        auth=FakeAuth(), api_client=SimpleNamespace(base_url="https://matrix.samta.ai"),
        projects=SimpleNamespace(get_project_names=lambda page_length=200: ["a", "b", "c"]),
        timesheets=SimpleNamespace(get_timesheets=lambda page_length=20: [1, 2]),
    )
    monkeypatch.setattr("src.cli.commands.tracker.get_context", lambda c, base_url=None: ctx)
    return ctx


def test_status_shows_everything_when_the_app_is_running(desktop, services):
    desktop.state = status_payload(active=True)
    out = run("status").output
    assert "jane@samta.ai" in out and "matrix.samta.ai" in out
    assert "running (tray)" in out and "active · every 15m · next prompt in 9m" in out
    assert "Projects" in out and "3" in out and "2 (latest 20)" in out


def test_status_when_the_app_is_not_running(monkeypatch, services):
    monkeypatch.setattr(ipc, "is_running", lambda: False)
    out = run("status").output
    assert "not running" in out and "samta-tracker start" in out


def test_status_when_not_logged_in_skips_counts_and_still_exits_0(monkeypatch, services):
    services.auth = FakeAuth(user=None)
    monkeypatch.setattr(ipc, "is_running", lambda: False)
    result = run("status")
    assert result.exit_code == 0 and "not logged in" in result.output and "Projects" in result.output


def test_status_json(desktop, services):
    desktop.state = status_payload(active=True)
    data = json.loads(run("--json", "status").output)
    assert data["logged_in"] is True and data["app_running"] is True
    assert data["tracker"]["active"] is True and data["projects"] == 3 and data["timesheet_rows"] == 2


# ── gui ───────────────────────────────────────────────────────────────────
def test_gui_raises_the_window_when_running(desktop):
    assert run("gui").exit_code == 0
    assert desktop.commands() == ["window.show"]


def test_gui_without_a_display_exits_4(monkeypatch):
    monkeypatch.setattr(ipc, "is_running", lambda: False)
    monkeypatch.setattr(gui_launcher, "display_available", lambda: False)
    assert run("gui").exit_code == 4


# ── remind ────────────────────────────────────────────────────────────────
def test_run_reminders_waits_the_interval_then_ticks():
    now = [1000.0]
    ticks, messages = [], []

    def sleep(seconds):
        now[0] += seconds

    count = tracker_cmd.run_reminders(
        120, lambda: ticks.append(now[0]), sleep=sleep, clock=lambda: now[0], max_ticks=2, announce=messages.append
    )
    assert count == 2 and ticks == [1120.0, 1240.0]
    assert len(messages) == 2 and "Next reminder at" in messages[0]


def test_run_reminders_stops_cleanly_on_ctrl_c():
    messages = []

    def sleep(_):
        raise KeyboardInterrupt

    assert tracker_cmd.run_reminders(60, lambda: None, sleep=sleep, clock=lambda: 0.0, announce=messages.append) == 0
    assert "Stopped reminders" in messages[-1]


def test_remind_needs_a_terminal():
    result = run("remind")
    assert result.exit_code == 2 and "interactive terminal" in result.output


def test_remind_rejects_a_bad_interval(monkeypatch):
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    assert run("remind", "--every", "10s").exit_code == 2


def test_log_prompt_declined_does_nothing(monkeypatch):
    called = []
    monkeypatch.setattr("src.cli.commands.log.add", SimpleNamespace(__wrapped__=lambda *a, **k: called.append(1)))
    monkeypatch.setattr(tracker_cmd.typer, "confirm", lambda *a, **k: False)
    tracker_cmd._log_prompt(SimpleNamespace())
    assert called == []


def test_log_prompt_uses_recent_entries_first_then_falls_back(monkeypatch):
    calls = []

    def add(ctx, **kwargs):
        calls.append(kwargs["recent"])
        if kwargs["recent"]:
            raise CliError("No recent entries to choose from.", 1)

    monkeypatch.setattr("src.cli.commands.log.add", SimpleNamespace(__wrapped__=add))
    monkeypatch.setattr(tracker_cmd.typer, "confirm", lambda *a, **k: True)
    tracker_cmd._log_prompt(SimpleNamespace())
    assert calls == [True, False]


def test_log_prompt_reports_a_failed_save_and_keeps_going(monkeypatch, capsys):
    def add(ctx, **kwargs):
        raise RuntimeError("server said no")

    monkeypatch.setattr("src.cli.commands.log.add", SimpleNamespace(__wrapped__=add))
    monkeypatch.setattr(tracker_cmd.typer, "confirm", lambda *a, **k: True)
    tracker_cmd._log_prompt(SimpleNamespace())
    assert "server said no" in capsys.readouterr().err


# ── launcher helpers ──────────────────────────────────────────────────────
def test_gui_command_for_a_source_checkout_and_a_packaged_build(monkeypatch):
    cmd = gui_launcher.gui_command(hidden=True)
    assert cmd[0] == sys.executable and cmd[-1] == "--hidden" and "gui_main" in cmd[2]
    assert gui_launcher.gui_command(hidden=False)[-1] != "--hidden"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    # Compare as paths (Windows uses backslashes) and pin the platform, which decides the .exe suffix.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "/opt/wt/samta-tracker")
    cmd = gui_launcher.gui_command(hidden=True)
    assert Path(cmd[0]) == Path("/opt/wt/WorkTracker") and cmd[1:] == ["--hidden"]
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "executable", "/opt/wt/samta-tracker.exe")
    assert Path(gui_launcher.gui_command(hidden=False)[0]) == Path("/opt/wt/WorkTracker.exe")


def test_log_add_asks_the_desktop_app_to_refresh_after_saving(monkeypatch):
    from tests.test_cli_log import FakeActivities, FakeProjects, FakeTimesheets

    sent = []
    monkeypatch.setattr(ipc, "request", lambda cmd, args=None, timeout=3.0: sent.append(cmd) or {})
    ctx = SimpleNamespace(projects=FakeProjects(), activities=FakeActivities(), timesheets=FakeTimesheets())
    monkeypatch.setattr("src.cli.commands.log.get_context", lambda c, base_url=None: ctx)
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: False)
    assert run("log", "add", "-p", "TATVA", "-a", "Execution", "-d", "x", "--duration", "5m").exit_code == 0
    assert sent == ["data.refresh"]


def test_a_failing_refresh_never_breaks_log_add(monkeypatch):
    from tests.test_cli_log import FakeActivities, FakeProjects, FakeTimesheets

    def boom(*a, **k):
        raise ipc.IpcUnavailable("gone")

    monkeypatch.setattr(ipc, "request", boom)
    ctx = SimpleNamespace(projects=FakeProjects(), activities=FakeActivities(), timesheets=FakeTimesheets())
    monkeypatch.setattr("src.cli.commands.log.get_context", lambda c, base_url=None: ctx)
    monkeypatch.setattr("src.cli.commands.log._interactive", lambda: False)
    assert run("log", "add", "-p", "TATVA", "-a", "Execution", "-d", "x", "--duration", "5m").exit_code == 0
