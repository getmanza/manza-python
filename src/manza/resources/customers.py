"""Mirrors lib/manza/resources/customers.rb."""

from __future__ import annotations

from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class Customers(ResourceBase):
    def list(
        self,
        *,
        q: str | None = None,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        return self.list_page("api/customers", {"q": q}, limit=limit, cursor=cursor)

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/customers", id))

    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/customers

        Accepts registration_number and vat_number. ``tax_id`` and ``ice_number``
        are market-gated: they are absent from requests and responses outside
        Morocco.
        """
        return self.http_post("api/customers", body=attributes)

    def update(self, id: str, **attributes: Any) -> ManzaResponse:
        return self.http_patch(self.encode_path("api/customers", id), body=attributes)

    def delete(self, id: str) -> ManzaResponse:
        return self.http_delete(self.encode_path("api/customers", id))
