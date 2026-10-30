"""Mirror of spec/manza/resources/transfer_authorizer_spec.rb."""

from __future__ import annotations


def test_get(make_client):
    manza = make_client(["transfer_authorizer/get"])
    response = manza.transfer_authorizer.get()
    assert response.status == 200
    assert response.body["status"] == "active"
    assert response.body["suspension_reason"] is None
    assert response.body["currency_code"] == "MAD"
    for key in (
        "per_transfer_limit",
        "daily_limit",
        "daily_authorized_total",
        "secret_expires_at",
        "webhook_endpoint_id",
        "enrolled_at",
    ):
        assert key in response.body
