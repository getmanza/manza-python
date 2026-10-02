"""Mirrors lib/zazu/transfer_authorization.rb.

Signs a machine-authorization challenge for an API-created transfer draft.
Pure functions, no HTTP.

The ``payment.authorization_requested`` webhook delivers the authorization id
and a one-time nonce. Build the signature input from your *own* record of the
transfer (not the webhook's ``signature_input``, which is there only to compare
against), sign it with the authorizer endpoint's signing secret, and pass the
result to ``TransferDrafts.authorize``::

    from zazu_sdk import transfer_authorization as ta

    signature_input = ta.signature_input(
        payment_id=draft["id"],
        nonce=nonce,
        amount=draft["amount"],
        currency_code=draft["currency_code"],
        account_id=draft["account_id"],
        payee=ta.payee_for(external_account_id=draft["external_account_id"]),
        client_reference=draft["client_reference"],
    )
    signature = ta.sign(signing_secret, signature_input)
    zazu.transfer_drafts.authorize(draft["id"], authorization_id, signature)
"""

from __future__ import annotations

import hashlib
import hmac

from .errors import ZazuArgumentError

SIGNATURE_VERSION = "manza.transfer-authorization.v1"


def signature_input(
    *,
    payment_id: str,
    nonce: str,
    amount: str,
    currency_code: str,
    account_id: str,
    payee: str,
    client_reference: str | None = None,
) -> str:
    """Build the versioned, pipe-joined input to sign.

    ``amount`` must be the API's decimal string verbatim (e.g. ``"2500.0"``).
    ``client_reference`` is empty when the transfer has none.
    """
    if not isinstance(amount, str):
        raise ZazuArgumentError(f"amount must be the API's decimal string (got {amount!r})")
    return "|".join(
        [
            SIGNATURE_VERSION,
            payment_id,
            nonce,
            amount,
            currency_code,
            account_id,
            payee,
            client_reference or "",
        ]
    )


def sign(secret: str, signature_input: str) -> str:
    """Lowercase hex HMAC-SHA256 of the signature input under the endpoint's signing secret."""
    return hmac.new(secret.encode(), signature_input.encode(), hashlib.sha256).hexdigest()


def payee_for(
    *, external_account_id: str | None = None, destination_account_id: str | None = None
) -> str:
    """The payee token: ``ext:<id>`` for a beneficiary's bank account, ``own:<id>`` for one
    of the entity's own accounts. Pass exactly one."""
    if (external_account_id is None) == (destination_account_id is None):
        raise ZazuArgumentError("pass exactly one of external_account_id or destination_account_id")
    if destination_account_id is not None:
        return f"own:{destination_account_id}"
    return f"ext:{external_account_id}"
