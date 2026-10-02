"""Mirrors lib/manza/resources/transfer_drafts.rb.

API-initiated transfers. Creating a draft never executes a transfer by itself.
A draft inside the entity's machine-authorization envelope (trusted payee,
within limits) is sent to the enrolled transfer authorizer as a
``payment.authorization_requested`` webhook; answer it with ``authorize`` or
``decline``, using an API key other than the one that created the draft. Every
other draft goes to the in-app approval flow, where a manager or legal
representative approves it. Poll ``get`` (status: requested -> processing ->
completed / failed) or subscribe to the ``transfer.executed`` webhook to follow
execution.
"""

from __future__ import annotations

from typing import Any

from ..errors import ManzaArgumentError
from ..response import ManzaResponse
from .base import ResourceBase


class TransferDrafts(ResourceBase):
    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/transfer_drafts

        Required: account_id, amount, and exactly one of beneficiary_id
        (external transfer) or destination_account_id (own-account move).
        Optional: external_account_id, currency_code, payment_reference,
        internal_notes, client_reference (unique per entity, at most 128
        characters; a duplicate raises ``ManzaConflictError`` whose
        ``payment_id`` names the existing draft). The response carries
        ``client_reference`` and ``authorization``.
        """
        return self.http_post("api/transfer_drafts", body=attributes)

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/transfer_drafts", id))

    def authorize(self, id: str, authorization_id: str, signature: str) -> ManzaResponse:
        """POST /api/transfer_drafts/:id/authorize

        Executes the draft. ``authorization_id`` comes from the
        ``payment.authorization_requested`` webhook; build ``signature`` with
        ``manza.transfer_authorization``. Requires the ``transfers:authorize``
        scope on a key other than the draft's creator (otherwise 403
        ``same_key_forbidden``). A blank signature is refused locally: the API
        counts it as a failed attempt, and five fail the challenge.
        """
        if not signature or not signature.strip():
            raise ManzaArgumentError("signature cannot be blank")
        return self.http_post(
            self.encode_path("api/transfer_drafts", id, "authorize"),
            body={"authorization_id": authorization_id, "signature": signature},
        )

    def decline(self, id: str, authorization_id: str, reason: str | None = None) -> ManzaResponse:
        """POST /api/transfer_drafts/:id/decline

        Declines the challenge and deletes the draft. Returns the authorization
        (``status: "declined"``). ``reason`` is omitted from the request when absent.
        """
        body: dict[str, Any] = {"authorization_id": authorization_id}
        if reason is not None:
            body["reason"] = reason
        return self.http_post(self.encode_path("api/transfer_drafts", id, "decline"), body=body)
