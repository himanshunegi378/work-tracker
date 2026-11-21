import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import keyring

from src.api import ApiClient
from src.persistence.session_store import SessionStore
from src.services.auth_service import AuthService

URL = "https://matrix.samta.ai"


class _Creds:
    def __init__(self):
        self.saved = None
        self.cleared = False

    def load_credentials(self):
        return None

    def save_credentials(self, creds):
        self.saved = creds
        return True

    def clear_credentials(self):
        self.cleared = True
        return True


def _client_with_cookie(value="abc"):
    client = ApiClient(base_url=URL)
    client.session.cookies.set("sid", value, domain="matrix.samta.ai", path="/", secure=True)
    return client


# ── cookie export / import ────────────────────────────────────────────────
def test_cookie_export_import_round_trip():
    exported = _client_with_cookie("s3").export_cookies()
    assert exported[0]["name"] == "sid" and exported[0]["value"] == "s3"
    other = ApiClient(base_url=URL)
    other.import_cookies(json.loads(json.dumps(exported)))
    assert other.session.cookies.get("sid", domain="matrix.samta.ai") == "s3"


def test_import_skips_malformed_cookies():
    client = ApiClient(base_url=URL)
    client.import_cookies([{"nope": 1}, None, {"name": "sid", "value": "ok", "domain": "matrix.samta.ai"}])
    assert client.session.cookies.get("sid", domain="matrix.samta.ai") == "ok"


# ── SessionStore ──────────────────────────────────────────────────────────
def test_store_round_trip_is_per_server():
    store = SessionStore()
    assert store.save(URL, [{"name": "sid", "value": "1"}])
    assert store.load(URL) == [{"name": "sid", "value": "1"}]
    assert store.load("https://other.example") is None
    store.clear(URL)
    assert store.load(URL) is None


def test_store_clear_when_empty_does_not_raise():
    SessionStore().clear(URL)


def test_store_ignores_garbage_and_keyring_failures(fake_keyring, monkeypatch):
    fake_keyring[("work-tracker", "session:matrix.samta.ai")] = "{not json"
    assert SessionStore().load(URL) is None

    def boom(*a, **k):
        raise RuntimeError("no keyring backend")

    monkeypatch.setattr(keyring, "get_password", boom)
    monkeypatch.setattr(keyring, "set_password", boom)
    monkeypatch.setattr(keyring, "delete_password", boom)
    store = SessionStore()
    assert store.load(URL) is None
    assert store.save(URL, []) is False
    store.clear(URL)  # no exception


# ── AuthService integration ───────────────────────────────────────────────
def _login_ok(client):
    client.get = mock.Mock()
    client.post = mock.Mock(return_value=SimpleNamespace(status_code=200, json=lambda: {"message": "Logged In"}))


def test_auth_service_restores_saved_session_at_startup():
    store = SessionStore()
    store.save(URL, _client_with_cookie("restored").export_cookies())
    client = ApiClient(base_url=URL)
    AuthService(client, _Creds(), session_store=store)
    assert client.session.cookies.get("sid", domain="matrix.samta.ai") == "restored"


def test_login_saves_session_for_other_process():
    store = SessionStore()
    client = _client_with_cookie("fresh")
    _login_ok(client)
    auth = AuthService(client, _Creds(), session_store=store)
    assert auth.login("jane", "pw") is True
    assert store.load(URL)[0]["value"] == "fresh"


def test_failed_login_does_not_overwrite_saved_session():
    store = SessionStore()
    store.save(URL, [{"name": "sid", "value": "keep"}])
    client = ApiClient(base_url=URL)
    client.get = mock.Mock()
    client.post = mock.Mock(return_value=SimpleNamespace(status_code=401, json=lambda: {}))
    auth = AuthService(client, _Creds(), session_store=store)
    assert auth.login("jane", "bad") is False
    assert store.load(URL) == [{"name": "sid", "value": "keep"}]


def test_logout_and_clear_credentials_remove_saved_session():
    store = SessionStore()
    store.save(URL, [{"name": "sid", "value": "1"}])
    creds = _Creds()
    auth = AuthService(ApiClient(base_url=URL), creds, session_store=store)
    auth.clear_saved_credentials()
    assert store.load(URL) is None
    assert creds.cleared


def test_auth_service_works_without_a_session_store():
    client = _client_with_cookie()
    _login_ok(client)
    assert AuthService(client, _Creds()).login("a", "b") is True
