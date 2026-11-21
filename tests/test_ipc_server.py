import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtWidgets import QApplication

from src.core import ipc
from src.ui.ipc_server import IpcServer
from src.ui.single_instance import SingleInstance


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def server(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, "endpoint_path", lambda: tmp_path / "ipc.json")
    calls = []

    def handler(cmd, args):
        calls.append((cmd, args))
        if cmd == "tracker.start" and args.get("every") == "bad":
            raise ipc.IpcCommandError("every must be a number")
        return {"echo": cmd, "thread_is_gui": threading.current_thread() is threading.main_thread()}

    srv = IpcServer(handler)
    assert srv.start()
    srv.calls = calls
    yield srv
    srv.stop()


def call_while_pumping(qapp, fn):
    """Run a blocking client call on another thread while the Qt loop serves it."""
    box = {}

    def work():
        try:
            box["result"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=work)
    thread.start()
    deadline = time.monotonic() + 5
    while thread.is_alive() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    thread.join(1)
    if "error" in box:
        raise box["error"]
    return box["result"]


def test_server_publishes_a_private_endpoint_and_removes_it_on_stop(server, tmp_path):
    endpoint = ipc.read_endpoint()
    assert endpoint.port == server.port and endpoint.pid == os.getpid()
    server.stop()
    assert ipc.read_endpoint() is None


def test_request_reaches_the_handler_on_the_gui_thread(server, qapp):
    data = call_while_pumping(qapp, lambda: ipc.request("tracker.status"))
    assert data == {"echo": "tracker.status", "thread_is_gui": True}


def test_arguments_are_passed_through(server, qapp):
    call_while_pumping(qapp, lambda: ipc.request("tracker.start", {"every": 900}))
    assert server.calls[-1] == ("tracker.start", {"every": 900})


def test_handler_errors_come_back_as_ipc_errors(server, qapp):
    with pytest.raises(ipc.IpcError, match="every must be a number"):
        call_while_pumping(qapp, lambda: ipc.request("tracker.start", {"every": "bad"}))


def test_wrong_token_never_reaches_the_handler(server, qapp):
    ipc.write_endpoint(server.port, "wrong-token")
    with pytest.raises(ipc.IpcError, match="Not authorized"):
        call_while_pumping(qapp, lambda: ipc.request("ping"))
    assert server.calls == []


def test_several_clients_in_a_row_are_all_served(server, qapp):
    for _ in range(5):
        assert call_while_pumping(qapp, lambda: ipc.request("ping"))["echo"] == "ping"


def test_oversized_garbage_is_dropped_without_a_crash(server, qapp):
    import socket

    def spam():
        with socket.create_connection((ipc.HOST, server.port), timeout=2) as conn:
            try:
                conn.sendall(b"x" * (ipc.MAX_MESSAGE_BYTES + 1000))
            except OSError:
                pass
        return True

    assert call_while_pumping(qapp, spam) is True
    assert call_while_pumping(qapp, lambda: ipc.request("ping"))["echo"] == "ping"


# ── single instance ───────────────────────────────────────────────────────
def test_only_one_instance_can_hold_the_lock(tmp_path):
    first, second = SingleInstance(tmp_path / "gui.lock"), SingleInstance(tmp_path / "gui.lock")
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()
