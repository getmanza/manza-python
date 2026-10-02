"""Mirror of spec/zazu/resources/payee_trust_requests_spec.rb."""

from __future__ import annotations

from tests.fixture_ids import FIXTURE_IDS


def test_create(make_client):
    zazu = make_client(["payee_trust_requests/create"], body_match="exact")
    external_account_id = FIXTURE_IDS["ZAZU_FIXTURE_EXTERNAL_ACCOUNT_ID"]
    response = zazu.payee_trust_requests.create(external_account_ids=[external_account_id])
    assert response.status == 201
    assert response.body["status"] == "pending"
    assert response.body["external_account_ids"] == [external_account_id]


def test_get(make_client):
    zazu = make_client(["payee_trust_requests/get"])
    trust_request_id = FIXTURE_IDS["ZAZU_FIXTURE_PAYEE_TRUST_REQUEST_ID"]
    response = zazu.payee_trust_requests.get(trust_request_id)
    assert response.body["id"] == trust_request_id
    assert response.body["resolved_at"] is None
