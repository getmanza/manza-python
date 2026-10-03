"""Mirror of spec/manza/resources/checkout_sessions_spec.rb."""

from __future__ import annotations

from tests.fixture_ids import FIXTURE_IDS


def test_create(make_client):
    manza = make_client(["checkout_sessions/create"])
    response = manza.checkout_sessions.create(
        account_id=FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
        amount="100.00",
        success_url="https://example.com/zazu-fixture-success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://example.com/zazu-fixture-cancel",
        description="Created by manza-ruby fixture spec",
        customer_email="fixture@example.com",
        metadata={"order_id": "ORD-FIXTURE"},
    )
    assert response.status == 201
    assert isinstance(response.body["id"], str)
    assert response.body["status"] == "open"


def test_get(make_client):
    manza = make_client(["checkout_sessions/get"])
    response = manza.checkout_sessions.get(FIXTURE_IDS["MANZA_FIXTURE_CHECKOUT_SESSION_ID"])
    assert isinstance(response.body["id"], str)
    assert isinstance(response.body["status"], str)
    assert "settled_at" in response.body
    assert "transaction" in response.body
    assert "billing_address" in response.body
