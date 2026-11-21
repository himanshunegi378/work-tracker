"""Parse dates for CLI flags: YYYY-MM-DD plus handy relative forms.

Accepted: 2026-11-21 · today · yesterday · tomorrow · -7d · +3d · -2w ·
monday..sunday (the most recent one on or before today).
"""

import re
from datetime import date, datetime, timedelta
from typing import Optional

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_ABBR = {d[:3]: i for i, d in enumerate(_WEEKDAYS)}
_REL = re.compile(r"^([+-])(\d+)([dw])$")
HELP = "YYYY-MM-DD, today, yesterday, -7d, -2w, or a weekday name"


def parse_date(text: str, today: Optional[date] = None) -> date:
    today = today or date.today()
    value = (text or "").strip().lower()
    if not value:
        raise ValueError(f"Date is empty. Use {HELP}.")
    if value == "today":
        return today
    if value == "yesterday":
        return today - timedelta(days=1)
    if value == "tomorrow":
        return today + timedelta(days=1)

    match = _REL.match(value)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        days = int(match.group(2)) * (7 if match.group(3) == "w" else 1)
        return today + timedelta(days=sign * days)

    weekday = _WEEKDAYS.index(value) if value in _WEEKDAYS else _ABBR.get(value)
    if weekday is not None:
        return today - timedelta(days=(today.weekday() - weekday) % 7)

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date '{text}'. Use {HELP}.") from None
