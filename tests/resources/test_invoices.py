"""Mirror of spec/manza/resources/invoices_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["invoices/list"])
    page = manza.invoices.list()
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["invoices/get"])
    response = manza.invoices.get(FIXTURE_IDS["MANZA_FIXTURE_INVOICE_ID"])
    assert isinstance(response.body["id"], str)


def test_create(make_client):
    manza = make_client(["invoices/create"])
    response = manza.invoices.create(
        customer_id=FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"],
        currency_code="MAD",
        issue_date="2026-05-03",
        due_date="2026-06-03",
        items=[{"description": "SDK fixture line", "quantity": 1, "unit_price": "100.00"}],
    )
    assert response.status == 201


def test_update(make_client):
    manza = make_client(["invoices/update"])
    response = manza.invoices.update(
        FIXTURE_IDS["MANZA_FIXTURE_INVOICE_ID"],
        notes="updated by SDK fixture spec",
    )
    assert response.status == 200


def test_delete(make_client):
    manza = make_client(["invoices/delete"])
    response = manza.invoices.delete(FIXTURE_IDS["MANZA_FIXTURE_DELETABLE_INVOICE_ID"])
    assert response.status == 204
