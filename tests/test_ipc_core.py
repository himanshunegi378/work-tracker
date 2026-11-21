import json
import os
import socket
import stat
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core import ipc


@pytest.fixture(autouse=True)
def isolated_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, "endpoint_path", lambda: tmp_path / "ipc.json")
    return tmp_path / "ipc.json"


def handler(cmd, args):
    if cmd == "tracker.start" and args.get("every") == "bad":
        raise ipc.IpcCommandError("every must be a number")
    if cmd == "app.quit":
        raise RuntimeError("boom")
    return {"cmd": cmd, "args": args}


def call(message, token="tok"):
    raw = json.dumps(message).encode() if not isinstance(message, bytes) else message
    return json.loads(ipc.process_request(raw, token, handler))


# ── process_request ───────────────────────────────────────────────────────
def test_valid_request_returns_handler_data():
    reply = call({"token": "tok", "cmd": "tracker.start", "args": {"every": 900}})
    assert reply == {"ok": True, "data": {"cmd": "tracker.start", "args": {"every": 900}}}


def test_wrong_or_missing_token_is_rejected():
    assert call({"token": "nope", "cmd": "ping"})["error"] == "Not authorized."
    assert call({"cmd": "ping"})["error"] == "Not authorized."


def test_unknown_command_and_bad_args():
    assert "Unknown command" in call({"token": "tok", "cmd": "rm -rf"})["error"]
    assert "object" in call({"token": "tok", "cmd": "ping", "args": [1]})["error"]


@pytest.mark.parametrize("raw", [b"not json", b"[1,2]", b"\xff\xfe", b""])
def test_malformed_requests(raw):
    assert call(raw)["ok"] is False


def test_command_error_message_is_passed_through_and_crashes_are_contained():
    assert call({"token": "tok", "cmd": "tracker.start", "args": {"every": "bad"}}) == {
        "ok": False, "error": "every must be a number"}
    crashed = call({"token": "tok", "cmd": "app.quit"})
    assert crashed["ok"] is False and "Internal error" in crashed["error"]


# ── endpoint file ─────────────────────────────────────────────────────────
def test_endpoint_roundtrip_and_permissions(isolated_endpoint):
    ipc.write_endpoint(4321, "secret")
    endpoint = ipc.read_endpoint()
    assert (endpoint.port, endpoint.token, endpoint.pid) == (4321, "secret", os.getpid())
    if sys.platform != "win32":
        assert stat.S_IMODE(isolated_endpoint.stat().st_mode) == 0o600


def test_remove_endpoint_only_when_the_token_matches():
    ipc.write_endpoint(1, "newer-instance")
    ipc.remove_endpoint("old-instance")
    assert ipc.read_endpoint() is not None
    ipc.remove_endpoint("newer-instance")
    assert ipc.read_endpoint() is None


def test_read_endpoint_handles_missing_and_corrupt_files(isolated_endpoint):
    assert ipc.read_endpoint() is None
    isolated_endpoint.write_text("{oops")
    assert ipc.read_endpoint() is None
    isolated_endpoint.write_text(json.dumps({"port": "x"}))
    assert ipc.read_endpoint() is None


# ── client ────────────────────────────────────────────────────────────────
def _serve_once(token, port_holder, ready):
    server = socket.socket()
    server.bind((ipc.HOST, 0))
    server.listen(1)
    port_holder.append(server.getsockname()[1])
    ready.set()
    conn, _ = server.accept()
    data = b""
    while b"\n" not in data:
        data += conn.recv(4096)
    conn.sendall(ipc.process_request(data.split(b"\n")[0], token, handler))
    conn.close()
    server.close()


def test_client_talks_to_a_real_socket_and_returns_data():
    port, ready = [], threading.Event()
    thread = threading.Thread(target=_serve_once, args=("tok", port, ready))
    thread.start()
    ready.wait(2)
    ipc.write_endpoint(port[0], "tok")
    assert ipc.request("tracker.start", {"every": 900}) == {"cmd": "tracker.start", "args": {"every": 900}}
    thread.join(2)


def test_client_raises_ipc_error_for_refused_commands():
    port, ready = [], threading.Event()
    thread = threading.Thread(target=_serve_once, args=("tok", port, ready))
    thread.start()
    ready.wait(2)
    ipc.write_endpoint(port[0], "tok")
    with pytest.raises(ipc.IpcError, match="every must be a number"):
        ipc.request("tracker.start", {"every": "bad"})
    thread.join(2)


def test_client_without_endpoint_is_unavailable():
    with pytest.raises(ipc.IpcUnavailable):
        ipc.request("ping")
    assert ipc.is_running() is False


def test_stale_endpoint_with_nothing_listening_is_unavailable():
    probe = socket.socket()
    probe.bind((ipc.HOST, 0))
    dead_port = probe.getsockname()[1]
    probe.close()  # nothing listens here any more
    ipc.write_endpoint(dead_port, "tok")
    with pytest.raises(ipc.IpcUnavailable):
        ipc.request("ping", timeout=0.5)
    assert ipc.is_running() is False


def test_wait_until_running_times_out():
    assert ipc.wait_until_running(0.3, interval=0.1) is False
