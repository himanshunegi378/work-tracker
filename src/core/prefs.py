"""User preferences shared by the GUI and the CLI (one JSON file in the app data dir).

Keys:
  url       backend base URL
  theme     "light" | "dark"
  interval  reminder interval (stored as seconds, shown like "15m")
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from src.core.durations import format_duration, parse_duration
from src.runtime_paths import user_data_dir

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://matrix.samta.ai"
THEMES = ("light", "dark")
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 24 * 3600

_DEFAULTS: Dict[str, Any] = {"url": DEFAULT_BASE_URL, "theme": "light", "interval": 15 * 60}


class PrefError(ValueError):
    """Raised for an unknown key or an invalid value."""


def keys() -> List[str]:
    return list(_DEFAULTS)


def prefs_path() -> Path:
    return user_data_dir() / "preferences.json"


def _read() -> Dict[str, Any]:
    try:
        data = json.loads(prefs_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        logger.warning("Ignoring unreadable preferences file", exc_info=True)
        return {}


def _write(data: Dict[str, Any]) -> None:
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def validate_url(value: str) -> str:
    url = (value or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise PrefError(f"Invalid URL '{value}'. Use a full address like https://example.com")
    return url


def _normalize(key: str, value: str) -> Any:
    if key == "url":
        return validate_url(value)
    if key == "theme":
        theme = value.strip().lower()
        if theme not in THEMES:
            raise PrefError(f"Invalid theme '{value}'. Choose one of: {', '.join(THEMES)}")
        return theme
    if key == "interval":
        try:
            seconds = parse_duration(value)
        except ValueError as exc:
            raise PrefError(str(exc)) from exc
        if not MIN_INTERVAL_SECONDS <= seconds <= MAX_INTERVAL_SECONDS:
            raise PrefError("Interval must be between 1m and 24h.")
        return seconds
    raise PrefError(f"Unknown setting '{key}'. Known settings: {', '.join(keys())}")


def _raw(key: str) -> Any:
    if key not in _DEFAULTS:
        raise PrefError(f"Unknown setting '{key}'. Known settings: {', '.join(keys())}")
    stored = _read().get(key)
    if stored is None:
        return _DEFAULTS[key]
    try:  # stored values are re-validated so a hand-edited file cannot break the app
        return _normalize(key, format_duration(stored) if key == "interval" else str(stored))
    except PrefError:
        logger.warning("Invalid stored value for %s; using default", key)
        return _DEFAULTS[key]


def get(key: str) -> str:
    """Return the setting as display text (interval as "15m")."""
    value = _raw(key)
    return format_duration(value) if key == "interval" else str(value)


def set_value(key: str, value: str) -> str:
    """Validate and save a setting; return its normalized display text."""
    normalized = _normalize(key, value)
    data = _read()
    data[key] = normalized
    _write(data)
    return get(key)


def get_all() -> Dict[str, str]:
    return {k: get(k) for k in keys()}


def get_url() -> str:
    return _raw("url")


def get_theme() -> str:
    return _raw("theme")


def get_interval_seconds() -> int:
    return _raw("interval")
