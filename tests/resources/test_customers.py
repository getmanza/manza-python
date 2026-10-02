"""Mirror of spec/manza/resources/customers_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["customers/list"])
    page = manza.customers.list()
    assert isinstance(page, Page)


def test_list_q_filtered(make_client):
    manza = make_client(["customers/list_q_filtered"])
    page = manza.customers.list(q="Acme")
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["customers/get"])
    response = manza.customers.get(FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"])
    assert isinstance(response.body["id"], str)


def test_create(make_client):
    manza = make_client(["customers/create"])
    response = manza.customers.create(
        customer_type="business",
        company_name="Manza SDK Fixture Co (manza-ruby-fixture-v1-spec)",
        email="create-spec@manza-ruby-fixture.example.com",
        ice_number="000000000000000",
    )
    assert response.status == 201
    assert isinstance(response.body["id"], str)


def test_update(make_client):
    manza = make_client(["customers/update"])
    response = manza.customers.update(
        FIXTURE_IDS["MANZA_FIXTURE_CUSTOMER_ID"],
        email="updated@example.com",
    )
    assert response.status == 200


def test_delete(make_client):
    manza = make_client(["customers/delete"])
    response = manza.customers.delete(FIXTURE_IDS["MANZA_FIXTURE_DELETABLE_CUSTOMER_ID"])
    assert response.status == 204
