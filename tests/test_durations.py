import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.durations import format_duration, parse_duration


@pytest.mark.parametrize(
    "text,seconds",
    [("1h30m", 5400), ("45m", 2700), ("90s", 90), ("15", 900), ("1.5h", 5400), (" 2h ", 7200), ("1H 5M", 3900)],
)
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("bad", ["", "abc", "1x", "h", "5m10", "-5m"])
def test_parse_duration_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


@pytest.mark.parametrize("seconds,text", [(5400, "1h30m"), (900, "15m"), (45, "45s"), (3600, "1h"), (3661, "1h1m1s"), (0, "0s")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_round_trip():
    for seconds in (60, 900, 5400, 86400):
        assert parse_duration(format_duration(seconds)) == seconds
