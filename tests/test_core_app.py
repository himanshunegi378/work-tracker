import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core import prefs
from src.core.app import DEFAULT_BASE_URL, AppContext, build_app


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "prefs_path", lambda: tmp_path / "preferences.json")


class _NoKeyring:
    """Stand-in for CredentialStorage so tests never touch the real keyring."""

    def load_credentials(self):
        return None


def _build(**kwargs):
    with mock.patch("src.core.app.CredentialStorage", _NoKeyring):
        return build_app(**kwargs)


def test_build_app_returns_all_services():
    ctx = _build()
    assert isinstance(ctx, AppContext)
    for name in ("api_client", "auth", "projects", "activities", "timesheets"):
        assert getattr(ctx, name) is not None


def test_build_app_shares_one_api_client():
    ctx = _build()
    assert ctx.auth.api_client is ctx.api_client
    assert ctx.projects.api_client is ctx.api_client
    assert ctx.activities.api_client is ctx.api_client
    assert ctx.timesheets.api_client is ctx.api_client


def test_session_recovery_is_wired_to_auth():
    ctx = _build()
    assert ctx.api_client.auth_provider == ctx.auth.ensure_session


def test_build_app_makes_no_network_calls():
    with mock.patch("requests.Session.request") as request:
        _build()
        request.assert_not_called()


def test_base_url_default_and_override():
    assert _build().api_client.base_url.rstrip("/") == DEFAULT_BASE_URL
    custom = _build(base_url="https://example.test")
    assert custom.api_client.base_url.rstrip("/") == "https://example.test"


def test_base_url_follows_saved_preference():
    prefs.set_value("url", "https://saved.example")
    assert _build().api_client.base_url == "https://saved.example"
    assert _build(base_url="https://explicit.example").api_client.base_url == "https://explicit.example"
