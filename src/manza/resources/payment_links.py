"""Mirrors lib/manza/resources/payment_links.rb."""

from __future__ import annotations

from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class PaymentLinks(ResourceBase):
    def list(
        self,
        *,
        status: str | None = None,
        link_type: str | None = None,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        return self.list_page(
            "api/payment_links",
            {"status": status, "link_type": link_type},
            limit=limit,
            cursor=cursor,
        )

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/payment_links", id))

    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/payment_links

        Accepts collect_billing_address and billing_address. Responses carry
        settled_at; ``status`` can be ``clearing`` (paid, awaiting settlement).
        """
        return self.http_post("api/payment_links", body=attributes)

    def cancel(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/payment_links", id, "cancel"))
