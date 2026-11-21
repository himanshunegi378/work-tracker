import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.core import prefs

runner = CliRunner()


class FakeAuth:
    def __init__(self, login_ok=True, session="jane@samta.ai", saved=("jane@samta.ai", "pw")):
        self.login_ok = login_ok
        self.session = session
        self.saved = saved
        self.login_calls = []
        self.cleared = False

    def login(self, username, password):
        self.login_calls.append((username, password))
        if self.login_ok:
            self.saved = (username, password)
            self.session = username
        return self.login_ok

    def getSession(self):
        return self.session

    def get_saved_username(self):
        return self.saved[0] if self.saved else None

    def get_saved_password(self):
        return self.saved[1] if self.saved else None

    def clear_saved_credentials(self):
        self.cleared = True
        self.saved = None
        self.session = None


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")


@pytest.fixture
def fake(monkeypatch):
    def install(auth):
        ctx = SimpleNamespace(auth=auth, api_client=SimpleNamespace(base_url="https://matrix.samta.ai"))
        monkeypatch.setattr("src.cli.commands.auth.get_context", lambda c, base_url=None: ctx)
        return auth

    return install


# ── config ────────────────────────────────────────────────────────────────
def test_config_get_all_and_one():
    result = runner.invoke(app, ["config", "get"])
    assert result.exit_code == 0
    assert "theme" in result.output and "15m" in result.output
    one = runner.invoke(app, ["config", "get", "interval"])
    assert one.output.strip() == "15m"


def test_config_set_and_get_roundtrip():
    assert runner.invoke(app, ["config", "set", "theme", "dark"]).exit_code == 0
    assert runner.invoke(app, ["config", "get", "theme"]).output.strip() == "dark"
    assert prefs.get_theme() == "dark"


def test_config_set_invalid_is_usage_error():
    result = runner.invoke(app, ["config", "set", "theme", "purple"])
    assert result.exit_code == 2
    assert "light, dark" in result.output


def test_config_unknown_key_is_usage_error():
    assert runner.invoke(app, ["config", "get", "nope"]).exit_code == 2
    assert runner.invoke(app, ["config", "set", "nope", "x"]).exit_code == 2


def test_config_json_output():
    data = json.loads(runner.invoke(app, ["--json", "config", "get"]).output)
    assert data == {"url": "https://matrix.samta.ai", "theme": "light", "interval": "15m"}
    one = json.loads(runner.invoke(app, ["--json", "config", "get", "theme"]).output)
    assert one == {"key": "theme", "value": "light"}


# ── login ─────────────────────────────────────────────────────────────────
def test_login_with_password_stdin(fake):
    auth = fake(FakeAuth())
    result = runner.invoke(app, ["login", "-u", "jane@samta.ai", "--password-stdin"], input="s3cret\n")
    assert result.exit_code == 0
    assert auth.login_calls == [("jane@samta.ai", "s3cret")]
    assert "Logged in" in result.output


def test_login_failure_exits_1(fake):
    fake(FakeAuth(login_ok=False))
    result = runner.invoke(app, ["login", "-u", "a", "--password-stdin"], input="bad\n")
    assert result.exit_code == 1
    assert "Login failed" in result.output


def test_login_without_terminal_or_username_is_usage_error(fake):
    fake(FakeAuth())
    assert runner.invoke(app, ["login"]).exit_code == 2
    assert runner.invoke(app, ["login", "--password-stdin"], input="pw\n").exit_code == 2


def test_login_empty_password_rejected(fake):
    auth = fake(FakeAuth())
    result = runner.invoke(app, ["login", "-u", "a", "--password-stdin"], input="\n")
    assert result.exit_code == 2
    assert auth.login_calls == []


def test_login_saves_url_only_after_success(fake):
    fake(FakeAuth(login_ok=False))
    runner.invoke(app, ["login", "-u", "a", "--password-stdin", "--url", "https://other.example"], input="x\n")
    assert prefs.get_url() == "https://matrix.samta.ai"
    fake(FakeAuth(login_ok=True))
    runner.invoke(app, ["login", "-u", "a", "--password-stdin", "--url", "https://other.example/"], input="x\n")
    assert prefs.get_url() == "https://other.example"


def test_login_rejects_bad_url(fake):
    fake(FakeAuth())
    result = runner.invoke(app, ["login", "-u", "a", "--password-stdin", "--url", "nope"], input="x\n")
    assert result.exit_code == 2


def test_login_json(fake):
    fake(FakeAuth())
    result = runner.invoke(app, ["--json", "login", "-u", "jane@samta.ai", "--password-stdin"], input="pw\n")
    assert json.loads(result.output) == {"logged_in": True, "user": "jane@samta.ai", "server": "matrix.samta.ai"}


# ── logout / status ───────────────────────────────────────────────────────
def test_logout_clears_credentials(fake):
    auth = fake(FakeAuth())
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert auth.cleared


def test_status_logged_in(fake):
    fake(FakeAuth())
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "matrix.samta.ai" in result.output and "jane@samta.ai" in result.output


def test_status_json(fake):
    fake(FakeAuth())
    data = json.loads(runner.invoke(app, ["--json", "auth", "status"]).output)
    assert data == {"logged_in": True, "user": "jane@samta.ai", "server": "matrix.samta.ai", "credentials_saved": True}


def test_status_not_logged_in_exits_3(fake):
    fake(FakeAuth(session=None, saved=None))
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 3
    assert "samta-tracker login" in result.output


def test_status_guest_with_saved_credentials_auto_logs_in(fake):
    auth = FakeAuth(session="Guest")
    fake(auth)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert auth.login_calls == [("jane@samta.ai", "pw")]
