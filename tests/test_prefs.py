import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core import prefs


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path, monkeypatch):
    path = tmp_path / "data" / "preferences.json"
    monkeypatch.setattr(prefs, "prefs_path", lambda: path)
    return path


def test_defaults():
    assert prefs.get_all() == {"url": "https://matrix.samta.ai", "theme": "light", "interval": "15m"}
    assert prefs.get_interval_seconds() == 900
    assert prefs.get_theme() == "light"


def test_set_persists_and_normalizes(isolated_prefs):
    assert prefs.set_value("theme", " DARK ") == "dark"
    assert prefs.set_value("interval", "1h30m") == "1h30m"
    assert prefs.set_value("url", "https://example.com/") == "https://example.com"
    assert prefs.get_theme() == "dark"
    assert prefs.get_interval_seconds() == 5400
    assert prefs.get_url() == "https://example.com"
    saved = json.loads(isolated_prefs.read_text())
    assert saved["interval"] == 5400  # stored as seconds


@pytest.mark.parametrize(
    "key,value",
    [("theme", "purple"), ("url", "matrix.samta.ai"), ("url", "ftp://x.y"), ("interval", "10s"), ("interval", "48h"), ("interval", "soon"), ("nope", "x")],
)
def test_invalid_values_rejected_and_not_saved(key, value, isolated_prefs):
    with pytest.raises(prefs.PrefError):
        prefs.set_value(key, value)
    assert not isolated_prefs.exists()


def test_unknown_key_on_get():
    with pytest.raises(prefs.PrefError):
        prefs.get("nope")


def test_corrupt_file_falls_back_to_defaults(isolated_prefs):
    isolated_prefs.parent.mkdir(parents=True)
    isolated_prefs.write_text("{not json")
    assert prefs.get_theme() == "light"


def test_hand_edited_invalid_value_falls_back(isolated_prefs):
    isolated_prefs.parent.mkdir(parents=True)
    isolated_prefs.write_text(json.dumps({"theme": "neon", "interval": 5}))
    assert prefs.get_theme() == "light"
    assert prefs.get_interval_seconds() == 900


def test_setting_one_key_keeps_others(isolated_prefs):
    prefs.set_value("theme", "dark")
    prefs.set_value("interval", "20m")
    assert prefs.get_theme() == "dark"
    assert prefs.get_interval_seconds() == 1200
