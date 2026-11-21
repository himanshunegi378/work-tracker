"""Parse and format human durations like "1h30m", "45m", "90s"."""

import re

_PART = re.compile(r"(\d+(?:\.\d+)?)\s*([hms])", re.IGNORECASE)
_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Return seconds. A bare number means minutes ("15" == 15 minutes)."""
    value = (text or "").strip().lower().replace(" ", "")
    if not value:
        raise ValueError("Duration is empty. Use values like 15m, 1h30m or 90s.")
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return round(float(value) * 60)
    if not re.fullmatch(r"(?:\d+(?:\.\d+)?[hms])+", value):
        raise ValueError(f"Invalid duration '{text}'. Use values like 15m, 1h30m or 90s.")
    return round(sum(float(n) * _UNIT_SECONDS[u] for n, u in _PART.findall(value)))


def format_duration(seconds: int) -> str:
    """Return the shortest readable form: 5400 -> "1h30m", 900 -> "15m", 45 -> "45s"."""
    seconds = int(seconds)
    if seconds <= 0:
        return "0s"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return "".join(parts)
