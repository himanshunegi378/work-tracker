import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.dates import parse_date

TODAY = date(2026, 11, 21)  # a Saturday


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-10-28", date(2026, 10, 28)),
        ("today", TODAY),
        ("Yesterday", date(2026, 11, 20)),
        ("tomorrow", date(2026, 11, 22)),
        ("-7d", date(2026, 11, 14)),
        ("+3d", date(2026, 11, 24)),
        ("-2w", date(2026, 11, 7)),
        ("saturday", TODAY),          # today is Saturday: "most recent, on or before today"
        ("monday", date(2026, 11, 16)),
        ("mon", date(2026, 11, 16)),
        ("sunday", date(2026, 11, 15)),
        (" -1d ", date(2026, 11, 20)),
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text, today=TODAY) == expected


@pytest.mark.parametrize("bad", ["", "soon", "2026-13-40", "26-11-21", "7d", "--7d", "1 week"])
def test_parse_date_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_date(bad, today=TODAY)
