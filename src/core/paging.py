"""Offset paging shared by every `list` command."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

DEFAULT_PAGE_SIZE = 20
DEFAULT_ALL_LIMIT = 250
MAX_LIMIT = 1000
_CHUNK = 100  # rows per request while collecting with --all

Fetch = Callable[[int, int], List[Dict[str, Any]]]  # (start, page_length) -> rows


@dataclass
class PageResult:
    rows: List[Dict[str, Any]]
    page: int
    limit: int
    more: bool          # the server may have more rows
    fetched_all: bool   # --all mode


def collect(fetch: Fetch, limit: Optional[int], page: int, all_pages: bool) -> PageResult:
    """Fetch one page, or (with all_pages) up to `limit` rows (default 250)."""
    if not all_pages:
        size = limit or DEFAULT_PAGE_SIZE
        rows = fetch((page - 1) * size, size)
        return PageResult(rows, page, size, more=len(rows) >= size, fetched_all=False)

    cap = limit or DEFAULT_ALL_LIMIT
    rows: List[Dict[str, Any]] = []
    more = False
    while len(rows) < cap:
        want = min(_CHUNK, cap - len(rows))
        batch = fetch(len(rows), want)
        rows.extend(batch)
        if len(batch) < want:
            break
    else:
        more = True  # stopped because the cap was reached; there may be more
    return PageResult(rows, 1, cap, more=more, fetched_all=True)


_SINGULAR = {"projects": "project", "activities": "activity", "timesheets": "timesheet"}


def footer(result: PageResult, noun: str) -> str:
    if not result.rows:
        return ""
    count = len(result.rows)
    if count == 1:
        noun = _SINGULAR.get(noun, noun)
    if result.fetched_all:
        tail = f" · capped at {result.limit}, raise with --limit" if result.more else ""
        return f"{count} {noun} shown (all pages){tail}"
    tail = f" · more may exist (--page {result.page + 1})" if result.more else ""
    return f"{count} {noun} shown · page {result.page}{tail}"
