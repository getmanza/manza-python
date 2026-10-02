"""Mirror of spec/zazu/resources/transfer_drafts_spec.rb."""

from __future__ import annotations

import httpx
import pytest

from tests.fixture_ids import FIXTURE_IDS, REPLAY_BASE_URL, TEST_API_KEY
from zazu_sdk import (
    Zazu,
    ZazuArgumentError,
    ZazuConflictError,
    ZazuForbiddenError,
    ZazuValidationError,
    transfer_authorization,
)

# Placeholder for the authorizer's signing secret: replay never reproduces the
# recorded HMAC (it signs the real nonce under the real secret), so the
# authorize cassettes match the body minus `signature`. The signer itself is
# proven by tests/test_transfer_authorization.py.
AUTHORIZER_SIGNING_SECRET = "whsec_replay_placeholder"


def test_create(make_client):
    zazu = make_client(["transfer_drafts/create"], body_match="exact")
    response = zazu.transfer_drafts.create(
        account_id=FIXTURE_IDS["ZAZU_FIXTURE_ACCOUNT_ID"],
        beneficiary_id=FIXTURE_IDS["ZAZU_FIXTURE_BENEFICIARY_ID"],
        amount="150.00",
        payment_reference="SDK fixture",
        client_reference=FIXTURE_IDS["ZAZU_FIXTURE_CLIENT_REFERENCE"],
    )
    assert response.status == 201
    assert response.body["status"] == "requested"
    assert response.body["client_reference"] == FIXTURE_IDS["ZAZU_FIXTURE_CLIENT_REFERENCE"]
    assert "authorization" in response.body
    assert response.body["transfer"] is None


def test_create_duplicate_client_reference(make_client):
    zazu = make_client(["transfer_drafts/create_duplicate"], body_match="exact")
    with pytest.raises(ZazuConflictError) as info:
        zazu.transfer_drafts.create(
            account_id=FIXTURE_IDS["ZAZU_FIXTURE_ACCOUNT_ID"],
            beneficiary_id=FIXTURE_IDS["ZAZU_FIXTURE_BENEFICIARY_ID"],
            amount="10.00",
            client_reference=FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_CLIENT_REFERENCE"],
        )
    assert info.value.status == 409
    assert info.value.type == "duplicate_client_reference"
    assert info.value.payment_id == FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_DRAFT_ID"]


def test_get(make_client):
    zazu = make_client(["transfer_drafts/get"])
    response = zazu.transfer_drafts.get(FIXTURE_IDS["ZAZU_FIXTURE_TRANSFER_DRAFT_ID"])
    assert isinstance(response.body["id"], str)
    assert "status" in response.body
    assert "transfer" in response.body


@pytest.mark.parametrize("signature", ["", " ", None])
def test_authorize_blank_signature_raises_before_any_http_call(signature):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call expected")

    zazu = Zazu(
        api_key=TEST_API_KEY,
        base_url=REPLAY_BASE_URL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ZazuArgumentError, match="signature"):
        zazu.transfer_drafts.authorize("draft", "auth", signature)


# Order matters while recording: five consecutive bad signatures suspend the
# authorizer, and only a valid authorize resets the streak. Replay is
# order-independent, one cassette per test.
def test_authorize_bad_signature(make_client):
    zazu = make_client(["transfer_drafts/authorize_bad_signature"], body_match="without_signature")
    with pytest.raises(ZazuValidationError) as info:
        zazu.transfer_drafts.authorize(
            FIXTURE_IDS["ZAZU_FIXTURE_BAD_SIGNATURE_DRAFT_ID"],
            FIXTURE_IDS["ZAZU_FIXTURE_BAD_SIGNATURE_AUTHORIZATION_ID"],
            "0" * 64,
        )
    assert info.value.type == "invalid_signature"


def test_authorize_with_the_creating_key(make_client):
    zazu = make_client(["transfer_drafts/authorize_same_key"], body_match="without_signature")
    with pytest.raises(ZazuForbiddenError) as info:
        zazu.transfer_drafts.authorize(
            FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_DRAFT_ID"],
            FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_AUTHORIZATION_ID"],
            "0" * 64,
        )
    assert info.value.type == "same_key_forbidden"


def test_authorize(make_client):
    zazu = make_client(["transfer_drafts/authorize"], body_match="without_signature")
    draft_id = FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_DRAFT_ID"]
    signature_input = transfer_authorization.signature_input(
        payment_id=draft_id,
        nonce=FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_NONCE"],
        amount="10.0",
        currency_code="MAD",
        account_id=FIXTURE_IDS["ZAZU_FIXTURE_ACCOUNT_ID"],
        payee=transfer_authorization.payee_for(
            external_account_id=FIXTURE_IDS["ZAZU_FIXTURE_TRUSTED_EXTERNAL_ACCOUNT_ID"]
        ),
        client_reference=FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_CLIENT_REFERENCE"],
    )
    response = zazu.transfer_drafts.authorize(
        draft_id,
        FIXTURE_IDS["ZAZU_FIXTURE_AUTHORIZABLE_AUTHORIZATION_ID"],
        transfer_authorization.sign(AUTHORIZER_SIGNING_SECRET, signature_input),
    )
    assert response.status == 200
    assert response.body["id"] == draft_id
    assert response.body["authorization"]["status"] == "authorized"


def test_decline(make_client):
    zazu = make_client(["transfer_drafts/decline"], body_match="exact")
    authorization_id = FIXTURE_IDS["ZAZU_FIXTURE_DECLINABLE_AUTHORIZATION_ID"]
    response = zazu.transfer_drafts.decline(
        FIXTURE_IDS["ZAZU_FIXTURE_DECLINABLE_DRAFT_ID"], authorization_id, "SDK fixture"
    )
    assert response.status == 200
    assert response.body["id"] == authorization_id
    assert response.body["status"] == "declined"
    assert isinstance(response.body["declined_at"], str)


def test_decline_omits_reason_when_absent():
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(
            200, headers={"content-type": "application/json"}, content=b'{"status":"declined"}'
        )

    zazu = Zazu(
        api_key=TEST_API_KEY,
        base_url=REPLAY_BASE_URL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    zazu.transfer_drafts.decline("draft", "auth")
    assert seen == [b'{"authorization_id":"auth"}']
