"""Mirrors lib/manza/resources/base.rb."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ..errors import ManzaArgumentError
from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse

if TYPE_CHECKING:
    from ..client import Manza


class ResourceBase:
    def __init__(self, client: Manza) -> None:
        self._client = client

    @staticmethod
    def encode_path(base: str, *segments: str) -> str:
        """Build a request path by joining a literal base path with dynamic
        segments. The base is appended verbatim; each dynamic segment is
        percent-encoded so an ID containing `/` or other special characters
        cannot escape the intended path.

            encode_path("api/accounts", "acc_xyz")
              # => "api/accounts/acc_xyz"
            encode_path("api/accounts", "acc 1", "transactions", "tx 1")
              # => "api/accounts/acc%201/transactions/tx%201"
        """
        encoded = []
        for seg in segments:
            text = str(seg)
            # An empty segment would silently turn `/things/:id` into
            # `/things/`, which on most APIs redispatches to the list
            # endpoint. Surface it loudly.
            if not text:
                raise ManzaArgumentError("path segment cannot be blank")
            encoded.append(quote(text, safe=""))
        return "/".join([base, *encoded])

    def http_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> ManzaResponse:
        return self._client.request("GET", path, params=params)

    def http_post(
        self,
        path: str,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> ManzaResponse:
        return self._client.request("POST", path, body=body, params=params)

    def http_patch(
        self,
        path: str,
        *,
        body: Any = None,
    ) -> ManzaResponse:
        return self._client.request("PATCH", path, body=body)

    def http_delete(self, path: str) -> ManzaResponse:
        return self._client.request("DELETE", path)

    def list_page(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Any]:
        merged: dict[str, Any] = dict(params or {})
        if limit is not None:
            merged["limit"] = min(limit, MAX_PER_PAGE)
        if cursor is not None:
            merged["cursor"] = cursor

        def fetch(next_cursor: str | None) -> Page[Any]:
            return self.list_page(path, params, limit=limit, cursor=next_cursor)

        response = self.http_get(path, params=merged)
        return Page(response, fetch)
