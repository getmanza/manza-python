"""Mirror of spec/manza/page_spec.rb."""

from __future__ import annotations

import httpx

from manza import MAX_PER_PAGE, Page
from manza.client import _parse_body  # type: ignore[attr-defined]
from manza.response import ManzaResponse


class _StubResponse:
    """Stand-in for ManzaResponse — Page only reads .body."""

    def __init__(self, body: dict) -> None:
        self.body = body


def test_max_per_page_is_100():
    assert MAX_PER_PAGE == 100


def test_page_exposes_data_has_more_next_cursor():
    response = _StubResponse(
        {"data": [{"id": "a"}, {"id": "b"}], "has_more": True, "next_cursor": "c"}
    )
    page: Page = Page(response, fetcher=lambda _c: page)  # type: ignore[arg-type, assignment]
    assert page.data == [{"id": "a"}, {"id": "b"}]
    assert page.has_more is True
    assert page.next_cursor == "c"
    assert len(page) == 2


def test_page_iter_yields_data():
    response = _StubResponse({"data": [1, 2, 3], "has_more": False, "next_cursor": None})
    page: Page = Page(response, fetcher=lambda _c: page)  # type: ignore[arg-type, assignment]
    assert list(page) == [1, 2, 3]


def test_page_next_returns_none_when_exhausted():
    response = _StubResponse({"data": [], "has_more": False, "next_cursor": None})
    page: Page = Page(response, fetcher=lambda _c: page)  # type: ignore[arg-type, assignment]
    assert page.next() is None


def test_auto_paging_iter_walks_pages():
    page2 = Page(
        _StubResponse({"data": [3, 4], "has_more": False, "next_cursor": None}),  # type: ignore[arg-type]
        fetcher=lambda _c: None,  # type: ignore[arg-type, return-value]
    )
    page1 = Page(
        _StubResponse({"data": [1, 2], "has_more": True, "next_cursor": "next"}),  # type: ignore[arg-type]
        fetcher=lambda _c: page2,
    )
    assert list(page1.auto_paging_iter()) == [1, 2, 3, 4]


def test_real_manza_response_works():
    """Sanity check: the stub above stands in for ManzaResponse, but Page also
    accepts the real one. This guards against `body` access drift."""
    raw = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=b'{"data":[1],"has_more":false,"next_cursor":null}',
    )
    response = ManzaResponse(raw, _parse_body(raw))
    page: Page = Page(response, fetcher=lambda _c: page)  # type: ignore[arg-type, assignment]
    assert page.data == [1]
