"""Mirror of spec/manza/resources/invoices_spec.rb."""

from __future__ import annotations

import re

import pytest

from manza import Manza, ManzaValidationError, Page
from tests.fixture_ids import FIXTURE_IDS, TEST_API_KEY


def test_list(make_client):
    manza = make_client(["invoices/list"])
    page = manza.invoices.list()
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["invoices/get"])
    response = manza.invoices.get(FIXTURE_IDS["MANZA_FIXTURE_INVOICE_ID"])
    assert isinstance(response.body["id"], str)


# Fixed dates keep the recorded body stable. The API refuses an issue date in a
# month before the entity's newest invoice number (the fixture entity has one in
# November 2026) or more than a month ahead.
def test_create_an_invoice_paid_into_the_account_asking_for_a_payment_link(make_client):
    manza = make_client(["invoices/create"], body_match="exact")
    response = manza.invoices.create(
        customer_id=FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"],
        account_id=FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
        currency_code="MAD",
        issue_date="2026-11-14",
        due_date="2026-12-14",
        generate_payment_link=True,
        items=[{"description": "SDK fixture line", "quantity": 1, "unit_price": "100.00"}],
    )
    assert response.status == 201
    assert response.body["generate_payment_link"] is True
    assert response.body["account"]["id"] == FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"]


# An invoice is paid into one of the entity's accounts: a create without one is
# refused as not approvable (`type` "state_error"). An account_id that is not
# the entity's is refused with `param` "account_id".
def test_create_without_an_account_id_raises_validation_error(make_client):
    manza = make_client(["invoices/create_without_account"], body_match="exact")
    with pytest.raises(ManzaValidationError) as info:
        manza.invoices.create(
            customer_id=FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"],
            currency_code="MAD",
            issue_date="2026-05-03",
            due_date="2026-06-03",
            items=[{"description": "SDK fixture line", "quantity": 1, "unit_price": "100.00"}],
        )
    assert info.value.status == 422
    assert info.value.type == "state_error"
    # The account refusal, not a date one (also state_error).
    assert info.value.param is None
    assert re.search(r"compte bancaire|bank account", info.value.message, re.IGNORECASE)


# Only a boolean (or "true"/"false"/"1"/"0") is taken: any other text is refused
# before anything is created.
def test_create_with_a_non_boolean_generate_payment_link_raises_validation_error_400(
    make_client,
):
    manza = make_client(["invoices/create_invalid_generate_payment_link"], body_match="exact")
    with pytest.raises(ManzaValidationError) as info:
        manza.invoices.create(
            customer_id=FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"],
            account_id=FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
            currency_code="MAD",
            issue_date="2026-05-03",
            due_date="2026-06-03",
            generate_payment_link="yes please",
            items=[{"description": "SDK fixture line", "quantity": 1, "unit_price": "100.00"}],
        )
    assert info.value.status == 400
    assert "generate_payment_link" in info.value.message


def test_update(make_client):
    manza = make_client(["invoices/update"], body_match="exact")
    response = manza.invoices.update(
        FIXTURE_IDS["MANZA_FIXTURE_INVOICE_ID"],
        account_id=FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
        notes="updated by SDK fixture spec",
        generate_payment_link=True,
    )
    assert response.status == 200
    assert response.body["generate_payment_link"] is True
    assert response.body["account"]["id"] == FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"]


def test_delete(make_client):
    manza = make_client(["invoices/delete"])
    response = manza.invoices.delete(FIXTURE_IDS["MANZA_FIXTURE_DELETABLE_INVOICE_ID"])
    assert response.status == 204


def test_has_no_create_payment_link_generate_payment_link_on_create_or_update_replaced_it():
    assert not hasattr(Manza(api_key=TEST_API_KEY).invoices, "create_payment_link")
