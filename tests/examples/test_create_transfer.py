"""The example's creator: it records the draft in the ledger from the API's
response and says where the API routed it. API calls go to an
`httpx.MockTransport`: no cassette, no network."""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
import pytest
from create_transfer import create
from ledger import Ledger

from manza import Manza

BASE_URL = "https://staging.manza.example"


def creator(
    status: int,
    body: dict[str, Any],
    seen: list[httpx.Request],
    headers: dict[str, str] | None = None,
) -> Manza:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            status,
            headers={"content-type": "application/json", **(headers or {})},
            content=json.dumps(body).encode(),
        )

    return Manza(
        api_key="key-a",
        base_url=BASE_URL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


DRAFT = {
    "id": "pay_1",
    "amount": "10.0",
    "currency_code": "MAD",
    "account_id": "acc_1",
    "external_account_id": "ext_1",
    "destination_account_id": None,
    "authorization": {"status": "refused", "refusal_reason": "over_transfer_limit"},
}


def run(manza: Manza, ledger: Ledger) -> str:
    out = io.StringIO()
    create(manza, ledger, amount="10.00", account_id="acc_1", beneficiary_id="ben_1", out=out)
    return out.getvalue()


def test_records_the_draft_from_the_response_and_says_where_it_went(tmp_path):
    seen: list[httpx.Request] = []
    ledger = Ledger(tmp_path / "ledger.json")

    output = run(creator(201, DRAFT, seen), ledger)

    [request] = seen
    assert request.url.path == "/api/payments"
    body = json.loads(request.content)
    client_reference = body["client_reference"]
    assert body["amount"] == "10.00"
    assert ledger.find(client_reference) == {
        "payment_id": "pay_1",
        "amount": "10.0",
        "currency_code": "MAD",
        "account_id": "acc_1",
        "payee": "ext:ext_1",
    }
    assert (
        f"created payment pay_1: 10.0 MAD to ext:ext_1 (client_reference {client_reference})"
        in output
    )
    assert "refused (over_transfer_limit)" in output


def test_an_own_account_move_records_an_own_payee(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    draft = {**DRAFT, "external_account_id": None, "destination_account_id": "acc_2"}

    output = run(creator(201, draft, []), ledger)

    assert "to own:acc_2" in output


def test_exits_with_the_error_type_and_request_id_when_create_fails(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    refused = {"error": {"type": "validation_error", "message": "amount is invalid"}}

    failed = r"create failed for client_reference example-.*'validation_error'.*'req_123'"
    with pytest.raises(SystemExit, match=failed):
        run(creator(422, refused, [], {"X-Request-Id": "req_123"}), ledger)
    assert not (tmp_path / "ledger.json").exists()
