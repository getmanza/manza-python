"""Mirrors lib/zazu/resources/checkout_sessions.rb."""

from __future__ import annotations

from typing import Any

from ..response import ZazuResponse
from .base import ResourceBase


class CheckoutSessions(ResourceBase):
    def get(self, id: str) -> ZazuResponse:
        return self.http_get(self.encode_path("api/checkout_sessions", id))

    def create(self, **attributes: Any) -> ZazuResponse:
        """POST /api/checkout_sessions

        Besides the required account_id, amount, success_url and cancel_url,
        accepts customer_name, collect_billing_address and billing_address.
        Responses carry settled_at and transaction; ``status`` can be
        ``clearing`` (paid, awaiting settlement).
        """
        return self.http_post("api/checkout_sessions", body=attributes)
