"""Fixed test vector, shared by every SDK in the family (see
spec/manza/transfer_authorization_spec.rb in manza-ruby). Each SDK's signer must
produce exactly these hex digests from these inputs. The digests were computed
independently with:

    printf '%s' '<input>' | openssl dgst -sha256 -hmac 'whsec_test_vector_secret'
"""

from __future__ import annotations

import pytest

from manza import ManzaArgumentError, transfer_authorization

SECRET = "whsec_test_vector_secret"
FIELDS = {
    "payment_id": "0199a1b2-0000-7000-8000-000000000001",
    "nonce": "n0nce-0123456789abcdef",
    "amount": "2500.0",
    "currency_code": "MAD",
    "account_id": "0199a1b2-0000-7000-8000-000000000002",
}


def test_signs_version_v2():
    assert transfer_authorization.SIGNATURE_VERSION == "manza.transfer-authorization.v2"


def test_external_account_payee_with_client_reference_and_transfer_method():
    payee = transfer_authorization.payee_for(
        external_account_id="0199a1b2-0000-7000-8000-000000000003"
    )
    signature_input = transfer_authorization.signature_input(
        **FIELDS, payee=payee, client_reference="po_1", transfer_method="eft"
    )

    assert signature_input == (
        "manza.transfer-authorization.v2|0199a1b2-0000-7000-8000-000000000001|"
        "n0nce-0123456789abcdef|2500.0|MAD|0199a1b2-0000-7000-8000-000000000002|"
        "ext:0199a1b2-0000-7000-8000-000000000003|po_1|eft"
    )
    assert transfer_authorization.sign(SECRET, signature_input) == (
        "904da7d0b73b2c919ffa1ae64d262ce5825ee4d2c8420fd70a3d257353e6c43a"
    )


def test_a_none_transfer_method_signs_an_empty_segment():
    payee = transfer_authorization.payee_for(
        external_account_id="0199a1b2-0000-7000-8000-000000000003"
    )
    signature_input = transfer_authorization.signature_input(
        **FIELDS, payee=payee, client_reference="po_1", transfer_method=None
    )

    assert signature_input.endswith("|ext:0199a1b2-0000-7000-8000-000000000003|po_1|")
    assert transfer_authorization.sign(SECRET, signature_input) == (
        "029dd12924a846d7af2f4aecb61e4f4f9bd64d37315230864fb03917adc29edf"
    )


def test_own_account_payee_without_client_reference_or_transfer_method():
    payee = transfer_authorization.payee_for(
        destination_account_id="0199a1b2-0000-7000-8000-000000000004"
    )
    signature_input = transfer_authorization.signature_input(
        **FIELDS, payee=payee, transfer_method=None
    )

    assert signature_input.endswith("|own:0199a1b2-0000-7000-8000-000000000004||")
    assert transfer_authorization.sign(SECRET, signature_input) == (
        "a21ccf43b94f23d7a595a36bd788c27c7adbc5686a5ad4427b22d9957568c9fb"
    )


def test_signature_input_refuses_a_non_string_amount():
    fields = {**FIELDS, "amount": 2500}
    with pytest.raises(ManzaArgumentError, match="amount"):
        transfer_authorization.signature_input(**fields, payee="ext:x", transfer_method=None)


# A v1 call (no transfer_method) fails here, not as a failed signature attempt
# at the API, where five of them fail the challenge.
def test_signature_input_requires_transfer_method_none_included():
    with pytest.raises(TypeError, match="transfer_method"):
        transfer_authorization.signature_input(**FIELDS, payee="ext:x")


def test_payee_for_refuses_both_ids():
    with pytest.raises(ManzaArgumentError):
        transfer_authorization.payee_for(external_account_id="a", destination_account_id="b")


def test_payee_for_refuses_neither_id():
    with pytest.raises(ManzaArgumentError):
        transfer_authorization.payee_for()
