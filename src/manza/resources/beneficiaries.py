"""Mirrors lib/manza/resources/beneficiaries.rb.

Saved transfer recipients. Each beneficiary embeds its bank accounts; the one
flagged ``default`` is used when a transfer names only the beneficiary_id.
There is no update or delete via the API.
"""

from __future__ import annotations

from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class Beneficiaries(ResourceBase):
    def list(self, *, limit: int = MAX_PER_PAGE, cursor: str | None = None) -> Page[Any]:
        return self.list_page("api/beneficiaries", {}, limit=limit, cursor=cursor)

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/beneficiaries", id))

    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/beneficiaries

        Keys: beneficiary_type ("individual" | "business"; inferred from
        person_name / company_name when omitted), person_name, company_name,
        email, phone_number. Values must be strings. Shares a 10/minute limit
        with ``create_external_account``.
        """
        return self.http_post("api/beneficiaries", body=attributes)

    def list_external_accounts(
        self, beneficiary_id: str, *, limit: int = MAX_PER_PAGE, cursor: str | None = None
    ) -> Page[Any]:
        """GET /api/beneficiaries/:beneficiary_id/external_accounts"""
        return self.list_page(
            self.encode_path("api/beneficiaries", beneficiary_id, "external_accounts"),
            {},
            limit=limit,
            cursor=cursor,
        )

    def get_external_account(self, beneficiary_id: str, id: str) -> ManzaResponse:
        """GET /api/beneficiaries/:beneficiary_id/external_accounts/:id"""
        return self.http_get(
            self.encode_path("api/beneficiaries", beneficiary_id, "external_accounts", id)
        )

    def create_external_account(self, beneficiary_id: str, **attributes: Any) -> ManzaResponse:
        """POST /api/beneficiaries/:beneficiary_id/external_accounts

        Required: account_number. Optional: name, country_code, currency_code,
        account_type ("bank" only), bank_identifier (required in ZA, rejected in
        MA, where it is derived from the RIB).
        """
        return self.http_post(
            self.encode_path("api/beneficiaries", beneficiary_id, "external_accounts"),
            body=attributes,
        )
