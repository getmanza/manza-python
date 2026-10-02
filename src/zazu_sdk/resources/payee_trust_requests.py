"""Mirrors lib/zazu/resources/payee_trust_requests.rb.

Requests to trust payees for machine-authorized transfers. The API key can
only ask: a member holding payment-authorize permission approves the request
in the Zazu app. Status: pending -> approved / declined / cancelled. There is
no list, update, or delete.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..response import ZazuResponse
from .base import ResourceBase


class PayeeTrustRequests(ResourceBase):
    def create(self, external_account_ids: Sequence[str]) -> ZazuResponse:
        """POST /api/payee_trust_requests. At most 100 bank accounts."""
        return self.http_post(
            "api/payee_trust_requests", body={"external_account_ids": list(external_account_ids)}
        )

    def get(self, id: str) -> ZazuResponse:
        return self.http_get(self.encode_path("api/payee_trust_requests", id))
