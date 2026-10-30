"""The creator process (key A). Creates a transfer draft, writes it to the
ledger from the API's response, and says where the API routed it::

    python create_transfer.py          # 10.00
    python create_transfer.py 250.00
"""

from __future__ import annotations

import os
import secrets
import sys
from typing import IO

import env_file
import routing
from ledger import Ledger

from manza import Manza, ManzaArgumentError, ManzaError, transfer_authorization


def create(
    creator: Manza,
    ledger: Ledger,
    *,
    amount: str,
    account_id: str,
    beneficiary_id: str,
    out: IO[str] = sys.stdout,
) -> None:
    """Exits with a message (status 1) when the draft cannot be created or recorded."""
    client_reference = f"example-{secrets.token_hex(6)}"
    try:
        draft = creator.payments.create(
            account_id=account_id,
            beneficiary_id=beneficiary_id,
            amount=amount,
            payment_reference="Transfer authorizer example",
            client_reference=client_reference,
        ).body
    except ManzaError as err:
        # A timeout may still have created the draft: look for this
        # client_reference in the app before rerunning, or the rerun creates a
        # second transfer.
        sys.exit(
            f"create failed for client_reference {client_reference}: {type(err).__name__}: "
            f"{err.message} (type {err.type!r}, request_id {err.request_id!r})"
        )

    destination = draft.get("destination_account_id")
    try:
        payee = transfer_authorization.payee_for(
            external_account_id=None if destination else draft.get("external_account_id"),
            destination_account_id=destination,
        )
    except ManzaArgumentError:
        sys.exit(
            f"payment {draft['id']} names neither an external_account_id nor a "
            "destination_account_id, so it was not written to the ledger: if it reaches the "
            "authorizer, the authorizer declines it"
        )
    try:
        ledger.record(
            client_reference,
            payment_id=draft["id"],
            amount=draft["amount"],
            currency_code=draft["currency_code"],
            account_id=draft["account_id"],
            payee=payee,
        )
    except Exception as err:
        sys.exit(
            f"payment {draft['id']} (client_reference {client_reference}) was created but not "
            f"written to the ledger ({type(err).__name__}: {err}): if it reaches the authorizer, "
            "the authorizer declines it"
        )
    print(
        f"created payment {draft['id']}: {draft['amount']} {draft['currency_code']} to {payee} "
        f"(client_reference {client_reference})",
        file=out,
    )
    print(routing.describe(draft.get("authorization")), file=out)


def main() -> None:
    env_file.load()
    create(
        Manza(api_key=os.environ["MANZA_CREATOR_API_KEY"]),
        Ledger(env_file.HERE / "ledger.json"),
        amount=sys.argv[1] if len(sys.argv) > 1 else "10.00",
        account_id=os.environ["MANZA_ACCOUNT_ID"],
        beneficiary_id=os.environ["MANZA_BENEFICIARY_ID"],
    )


if __name__ == "__main__":
    main()
