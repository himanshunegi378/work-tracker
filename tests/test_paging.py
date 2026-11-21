import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import paging


def make_fetch(total):
    calls = []

    def fetch(start, count):
        calls.append((start, count))
        return [{"i": i} for i in range(start, min(start + count, total))]

    fetch.calls = calls
    return fetch


def test_single_page_offsets():
    fetch = make_fetch(100)
    result = paging.collect(fetch, limit=10, page=3, all_pages=False)
    assert fetch.calls == [(20, 10)]
    assert [r["i"] for r in result.rows][:2] == [20, 21]
    assert result.more is True and result.page == 3 and not result.fetched_all


def test_default_page_size_is_20_and_last_page_has_no_more():
    fetch = make_fetch(25)
    assert paging.collect(fetch, None, 1, False).limit == 20
    last = paging.collect(make_fetch(25), None, 2, False)
    assert len(last.rows) == 5 and last.more is False


def test_all_collects_every_row_when_under_cap():
    fetch = make_fetch(130)
    result = paging.collect(fetch, None, 1, True)
    assert len(result.rows) == 130 and result.more is False
    assert fetch.calls == [(0, 100), (100, 100)]


def test_all_is_capped_at_250_by_default():
    fetch = make_fetch(1000)
    result = paging.collect(fetch, None, 1, True)
    assert len(result.rows) == 250 and result.more is True
    assert fetch.calls == [(0, 100), (100, 100), (200, 50)]


def test_all_respects_custom_limit():
    result = paging.collect(make_fetch(1000), 120, 1, True)
    assert len(result.rows) == 120 and result.more is True


def test_all_exact_fit_still_reports_possible_more():
    result = paging.collect(make_fetch(250), None, 1, True)
    assert len(result.rows) == 250 and result.more is True  # cap reached: cannot know


def test_empty_result():
    result = paging.collect(make_fetch(0), None, 1, True)
    assert result.rows == [] and paging.footer(result, "projects") == ""


def test_footer_wording():
    page = paging.collect(make_fetch(100), 10, 1, False)
    assert paging.footer(page, "projects") == "10 projects shown · page 1 · more may exist (--page 2)"
    one = paging.collect(make_fetch(1), 10, 1, False)
    assert paging.footer(one, "activities") == "1 activity shown · page 1"
    capped = paging.collect(make_fetch(1000), None, 1, True)
    assert "capped at 250" in paging.footer(capped, "timesheets")
