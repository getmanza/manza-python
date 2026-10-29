"""Mirrors lib/manza/resources/payments.rb.

API-initiated transfers, called payments (formerly transfer drafts;
``/api/transfer_drafts`` stays a permanent server-side alias). Creating a draft
never executes a transfer by itself. A draft inside the entity's
machine-authorization envelope (trusted payee, within limits) is sent to the
enrolled transfer authorizer as a ``payment.authorization_requested`` webhook;
answer it with ``authorize`` or ``decline``, using an API key other than the one
that created the draft. Every other draft goes to the in-app approval flow,
where a manager or legal representative approves it. Poll ``get`` (status:
requested -> processing -> completed / failed) or subscribe to the
``transfer.executed`` webhook to follow execution.

A draft's ``authorization`` says which way it went: ``pending`` (a challenge was
sent), ``authorized``, ``declined`` (the draft is deleted), or one of two
outcomes that send the draft to the in-app approvers, each with a
``refusal_reason``:

- ``refused``: it did not qualify, at create time (no webhook is sent) or again
  when the challenge was answered: ``untrusted_payee``, ``unrestricted_api_key``,
  ``over_new_payee_limit``, ``over_transfer_limit``, ``over_daily_limit``,
  ``currency_mismatch``, ``suspended`` or ``secret_expired``.
- ``expired`` / ``superseded`` / ``failed``: a challenge was sent and closed
  without an authorize: ``expired`` (no answer within the hour), ``stale`` (the
  draft, its payee's bank details or the endpoint changed while it was open) or
  ``signature_failed`` (five invalid signatures). One exception: the in-app
  approval that finalizes the draft while its challenge is open supersedes it
  (``stale``), and the draft executes or is scheduled; its ``status`` shows which.

``authorization`` is None when no authorizer was enrolled.

With "Approve transfers to new payees" on (enrolment, in the app), a draft to
bank details the entity never trusted is challenged too, up to the new-payee
limit, when the creating key has an IP allowlist; authorizing it also trusts
the payee.
"""

from __future__ import annotations

from typing import Any

from ..errors import ManzaArgumentError
from ..response import ManzaResponse
from .base import ResourceBase


class Payments(ResourceBase):
    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/payments

        Required: account_id, amount, and exactly one of beneficiary_id
        (external transfer) or destination_account_id (own-account move).
        Optional: external_account_id, currency_code, payment_reference,
        internal_notes, client_reference (unique per entity, at most 128
        characters; a duplicate raises ``ManzaConflictError`` whose
        ``payment_id`` names the existing draft). The response carries
        ``client_reference`` and ``authorization``.
        """
        return self.http_post("api/payments", body=attributes)

    def get(self, id: str) -> ManzaResponse:
        """GET /api/payments/:id"""
        return self.http_get(self.encode_path("api/payments", id))

    def authorize(self, id: str, authorization_id: str, signature: str) -> ManzaResponse:
        """POST /api/payments/:id/authorize

        Executes the draft. ``authorization_id`` comes from the
        ``payment.authorization_requested`` webhook; build ``signature`` with
        ``manza.transfer_authorization``. Requires the ``transfers:authorize``
        scope on a key other than the draft's creator (otherwise 403
        ``same_key_forbidden``), bound to an IP allowlist (otherwise 403
        ``unrestricted_api_key``). A 409 ``ManzaConflictError`` with ``type``
        ``authorization_busy`` means a bank-detail edit, trust or trust
        revocation on the payee was in flight: retry. A blank signature raises
        ``ManzaArgumentError`` and is never sent: the API would count it as a
        failed attempt. Five invalid signatures fail the challenge.
        """
        if not signature or not signature.strip():
            raise ManzaArgumentError("signature cannot be blank")
        return self.http_post(
            self.encode_path("api/payments", id, "authorize"),
            body={"authorization_id": authorization_id, "signature": signature},
        )

    def decline(self, id: str, authorization_id: str, reason: str | None = None) -> ManzaResponse:
        """POST /api/payments/:id/decline

        Declines the challenge and deletes the draft. Returns the authorization
        (``status: "declined"``, ``declined_at``, and a None ``refusal_reason``).
        ``reason`` is omitted from the request when absent.
        """
        body: dict[str, Any] = {"authorization_id": authorization_id}
        if reason is not None:
            body["reason"] = reason
        return self.http_post(self.encode_path("api/payments", id, "decline"), body=body)
