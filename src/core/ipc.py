"""Tiny local protocol between the CLI and the running desktop app.

The app listens on 127.0.0.1 (random port) and publishes `{port, token, pid}` in
`ipc.json` (owner-readable only). A client sends one JSON line
`{"token": ..., "cmd": ..., "args": {...}}` and gets one JSON line back
`{"ok": true, "data": {...}}` or `{"ok": false, "error": "..."}`.

This module is Qt-free (standard library only) so the CLI stays fast.
"""

import json
import logging
import os
import secrets
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.runtime_paths import user_data_dir

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
MAX_MESSAGE_BYTES = 64 * 1024
DEFAULT_TIMEOUT = 3.0

COMMANDS = (
    "ping", "tracker.start", "tracker.stop", "tracker.status",
    "window.show", "app.quit", "data.refresh",
)


class IpcUnavailable(Exception):
    """The desktop app is not running (or not reachable)."""


class IpcError(Exception):
    """The app answered, but refused or failed the request."""


class IpcCommandError(Exception):
    """Raised by a handler for a bad command or argument (message is user-facing)."""


@dataclass(frozen=True)
class Endpoint:
    port: int
    token: str
    pid: int


def endpoint_path() -> Path:
    return user_data_dir() / "ipc.json"


def new_token() -> str:
    return secrets.token_hex(16)


def write_endpoint(port: int, token: str) -> None:
    """Publish how to reach this app. The file is private to the current user."""
    path = endpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"port": port, "token": token, "pid": os.getpid()}, handle)
    os.replace(tmp, path)


def read_endpoint() -> Optional[Endpoint]:
    try:
        data = json.loads(endpoint_path().read_text(encoding="utf-8"))
        return Endpoint(port=int(data["port"]), token=str(data["token"]), pid=int(data.get("pid", 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remove_endpoint(token: str) -> None:
    """Delete the endpoint file, but only if it is still ours (a newer app may own it)."""
    current = read_endpoint()
    if current is not None and current.token == token:
        try:
            endpoint_path().unlink()
        except OSError:
            pass


# ── client ────────────────────────────────────────────────────────────────
def request(cmd: str, args: Optional[Dict[str, Any]] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Send one command to the running app and return its `data`.

    Raises IpcUnavailable if the app isn't running, IpcError if it refuses.
    """
    endpoint = read_endpoint()
    if endpoint is None:
        raise IpcUnavailable("The desktop app is not running.")
    payload = json.dumps({"token": endpoint.token, "cmd": cmd, "args": args or {}}).encode("utf-8") + b"\n"
    try:
        with socket.create_connection((HOST, endpoint.port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(payload)
            buffer = b""
            while b"\n" not in buffer:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > MAX_MESSAGE_BYTES:
                    raise IpcError("Response too large.")
    except (ConnectionError, socket.timeout, OSError) as exc:
        raise IpcUnavailable("The desktop app is not responding.") from exc

    try:
        reply = json.loads(buffer.split(b"\n", 1)[0].decode("utf-8"))
    except ValueError as exc:
        raise IpcError("Unreadable response from the desktop app.") from exc
    if not reply.get("ok"):
        raise IpcError(str(reply.get("error") or "Request failed."))
    return reply.get("data") or {}


def is_running() -> bool:
    try:
        request("ping", timeout=1.0)
        return True
    except (IpcUnavailable, IpcError):
        return False


def wait_until_running(timeout: float, interval: float = 0.2) -> bool:
    """Poll until the app answers a ping (used right after launching it)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running():
            return True
        time.sleep(interval)
    return False


# ── server-side helper (pure, so it can be tested without Qt) ─────────────
Handler = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def process_request(raw: bytes, token: str, handler: Handler) -> bytes:
    """Validate one request line and return the encoded reply line."""

    def reply(ok: bool, **fields: Any) -> bytes:
        return json.dumps({"ok": ok, **fields}, default=str).encode("utf-8") + b"\n"

    try:
        message = json.loads(raw.decode("utf-8"))
        if not isinstance(message, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return reply(False, error="Malformed request.")

    if not secrets.compare_digest(str(message.get("token", "")), token):
        return reply(False, error="Not authorized.")
    cmd, args = message.get("cmd"), message.get("args") or {}
    if cmd not in COMMANDS:
        return reply(False, error=f"Unknown command '{cmd}'.")
    if not isinstance(args, dict):
        return reply(False, error="Arguments must be an object.")
    try:
        return reply(True, data=handler(cmd, args) or {})
    except IpcCommandError as exc:
        return reply(False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - never let a handler bug kill the server
        logger.exception("IPC handler failed for %s", cmd)
        return reply(False, error=f"Internal error: {exc}")
