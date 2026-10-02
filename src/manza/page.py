"""Mirrors lib/manza/page.rb. Cursor-based pagination, hard cap of 100 items per page."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Generic, TypeVar

from .response import ManzaResponse

MAX_PER_PAGE = 100

T = TypeVar("T")


class Page(Generic[T]):
    """A single page of results plus a fetcher to load the next page on demand."""

    def __init__(
        self,
        response: ManzaResponse,
        fetcher: Callable[[str | None], "Page[T]"],
    ) -> None:
        self.response = response
        self._fetcher = fetcher
        body = response.body if isinstance(response.body, dict) else {}
        self.data: list[T] = list(body.get("data") or [])
        self.has_more: bool = bool(body.get("has_more"))
        self.next_cursor: str | None = body.get("next_cursor")

    def next(self) -> Page[T] | None:
        """Fetch the next page, or None if there are no more results."""
        if not self.has_more or not self.next_cursor:
            return None
        return self._fetcher(self.next_cursor)

    def auto_paging_iter(self) -> Iterator[T]:
        """Yield every item across all pages by chasing cursors."""
        page: Page[T] | None = self
        while page is not None:
            yield from page.data
            page = page.next()

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"Page(items={len(self.data)}, has_more={self.has_more})"


PageBody = dict[str, Any]
PageFetcher = Callable[[str | None], Page[Any]]
