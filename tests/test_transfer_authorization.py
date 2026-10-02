"""Fixed test vector, shared by every SDK in the family (see
spec/zazu/transfer_authorization_spec.rb in zazu-ruby). Each SDK's signer must
produce exactly these hex digests from these inputs. The digests were computed
independently with:

    printf '%s' '<input>' | openssl dgst -sha256 -hmac 'whsec_test_vector_secret'
"""

from __future__ import annotations

import pytest

from zazu_sdk import ZazuArgumentError, transfer_authorization

SECRET = "whsec_test_vector_secret"
FIELDS = {
    "payment_id": "0199a1b2-0000-7000-8000-000000000001",
    "nonce": "n0nce-0123456789abcdef",
    "amount": "2500.0",
    "currency_code": "MAD",
    "account_id": "0199a1b2-0000-7000-8000-000000000002",
}


def test_external_account_payee_with_client_reference():
    payee = transfer_authorization.payee_for(
        external_account_id="0199a1b2-0000-7000-8000-000000000003"
    )
    signature_input = transfer_authorization.signature_input(
        **FIELDS, payee=payee, client_reference="po_1"
    )

    assert signature_input == (
        "manza.transfer-authorization.v1|0199a1b2-0000-7000-8000-000000000001|"
        "n0nce-0123456789abcdef|2500.0|MAD|0199a1b2-0000-7000-8000-000000000002|"
        "ext:0199a1b2-0000-7000-8000-000000000003|po_1"
    )
    assert transfer_authorization.sign(SECRET, signature_input) == (
        "6e8eaec0f89a4eb3b22df1133b3d6dfebfa8505c34c58ed0ff192516e4223078"
    )


def test_own_account_payee_without_client_reference():
    payee = transfer_authorization.payee_for(
        destination_account_id="0199a1b2-0000-7000-8000-000000000004"
    )
    signature_input = transfer_authorization.signature_input(**FIELDS, payee=payee)

    assert signature_input.endswith("|own:0199a1b2-0000-7000-8000-000000000004|")
    assert transfer_authorization.sign(SECRET, signature_input) == (
        "af9440b1de1bebb51f381ce43e3d0d27b6a4ccb99dcd548c0b5435ff4fdd1895"
    )


def test_signature_input_refuses_a_non_string_amount():
    fields = {**FIELDS, "amount": 2500}
    with pytest.raises(ZazuArgumentError, match="amount"):
        transfer_authorization.signature_input(**fields, payee="ext:x")


def test_payee_for_refuses_both_ids():
    with pytest.raises(ZazuArgumentError):
        transfer_authorization.payee_for(external_account_id="a", destination_account_id="b")


def test_payee_for_refuses_neither_id():
    with pytest.raises(ZazuArgumentError):
        transfer_authorization.payee_for()
