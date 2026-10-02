"""Mirrors lib/manza/resources/accounts.rb."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class Accounts(ResourceBase):
    def list(
        self,
        *,
        status: str | None = None,
        currency_code: str | None = None,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        return self.list_page(
            "api/accounts",
            {"status": status, "currency_code": currency_code},
            limit=limit,
            cursor=cursor,
        )

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/accounts", id))

    def list_transactions(
        self,
        account_id: str,
        *,
        operation: str | None = None,
        posted_after: str | datetime | None = None,
        posted_before: str | datetime | None = None,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        return self.list_page(
            self.encode_path("api/accounts", account_id, "transactions"),
            {
                "operation": operation,
                "posted_after": _serialize_time(posted_after),
                "posted_before": _serialize_time(posted_before),
            },
            limit=limit,
            cursor=cursor,
        )

    def get_transaction(self, account_id: str, transaction_id: str) -> ManzaResponse:
        return self.http_get(
            self.encode_path("api/accounts", account_id, "transactions", transaction_id)
        )


def _serialize_time(value: str | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
