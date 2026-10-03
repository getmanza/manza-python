"""Mirror of spec/manza/resources/beneficiaries_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["beneficiaries/list"])
    page = manza.beneficiaries.list()
    assert isinstance(page, Page)
    assert isinstance(page.data[0]["external_accounts"], list)


def test_get(make_client):
    manza = make_client(["beneficiaries/get"])
    response = manza.beneficiaries.get(FIXTURE_IDS["MANZA_FIXTURE_BENEFICIARY_ID"])
    assert isinstance(response.body["id"], str)
    assert isinstance(response.body["external_accounts"], list)


def test_create(make_client):
    manza = make_client(["beneficiaries/create"], body_match="exact")
    response = manza.beneficiaries.create(
        beneficiary_type="business",
        company_name="Zazu Fixture Beneficiary - spec (zazu-ruby-fixture)",
        email="fixture-beneficiary-spec@example.com",
    )
    assert response.status == 201
    assert response.body["beneficiary_type"] == "business"
    assert response.body["external_accounts"] == []


def test_list_external_accounts(make_client):
    manza = make_client(["beneficiaries/list_external_accounts"])
    page = manza.beneficiaries.list_external_accounts(
        FIXTURE_IDS["MANZA_FIXTURE_CREATED_BENEFICIARY_ID"]
    )
    assert isinstance(page, Page)
    assert page.data[0]["id"] == FIXTURE_IDS["MANZA_FIXTURE_EXTERNAL_ACCOUNT_ID"]
    assert isinstance(page.data[0]["account_number"], str)
    assert page.has_more is False
    assert page.next_cursor is None


def test_get_external_account(make_client):
    manza = make_client(["beneficiaries/get_external_account"])
    response = manza.beneficiaries.get_external_account(
        FIXTURE_IDS["MANZA_FIXTURE_CREATED_BENEFICIARY_ID"],
        FIXTURE_IDS["MANZA_FIXTURE_EXTERNAL_ACCOUNT_ID"],
    )
    assert response.body["id"] == FIXTURE_IDS["MANZA_FIXTURE_EXTERNAL_ACCOUNT_ID"]
    assert "default" in response.body


def test_create_external_account(make_client):
    manza = make_client(["beneficiaries/create_external_account"], body_match="exact")
    response = manza.beneficiaries.create_external_account(
        FIXTURE_IDS["MANZA_FIXTURE_CREATED_BENEFICIARY_ID"],
        account_number=FIXTURE_IDS["MANZA_FIXTURE_NEW_ACCOUNT_NUMBER"],
        name="Fixture Secondary Account",
    )
    assert response.status == 201
    assert response.body["name"] == "Fixture Secondary Account"
    assert response.body["default"] is False
