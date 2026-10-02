"""Mirror of spec/zazu/resources/beneficiaries_spec.rb."""

from __future__ import annotations

from tests.fixture_ids import FIXTURE_IDS
from zazu_sdk import Page


def test_list(make_client):
    zazu = make_client(["beneficiaries/list"])
    page = zazu.beneficiaries.list()
    assert isinstance(page, Page)
    assert isinstance(page.data[0]["external_accounts"], list)


def test_get(make_client):
    zazu = make_client(["beneficiaries/get"])
    response = zazu.beneficiaries.get(FIXTURE_IDS["ZAZU_FIXTURE_BENEFICIARY_ID"])
    assert isinstance(response.body["id"], str)
    assert isinstance(response.body["external_accounts"], list)


def test_create(make_client):
    zazu = make_client(["beneficiaries/create"], body_match="exact")
    response = zazu.beneficiaries.create(
        beneficiary_type="business",
        company_name="Zazu Fixture Beneficiary - spec (zazu-ruby-fixture)",
        email="fixture-beneficiary-spec@example.com",
    )
    assert response.status == 201
    assert response.body["beneficiary_type"] == "business"
    assert response.body["external_accounts"] == []


def test_list_external_accounts(make_client):
    zazu = make_client(["beneficiaries/list_external_accounts"])
    page = zazu.beneficiaries.list_external_accounts(
        FIXTURE_IDS["ZAZU_FIXTURE_CREATED_BENEFICIARY_ID"]
    )
    assert isinstance(page, Page)
    assert page.data[0]["id"] == FIXTURE_IDS["ZAZU_FIXTURE_EXTERNAL_ACCOUNT_ID"]
    assert isinstance(page.data[0]["account_number"], str)
    assert page.has_more is False
    assert page.next_cursor is None


def test_get_external_account(make_client):
    zazu = make_client(["beneficiaries/get_external_account"])
    response = zazu.beneficiaries.get_external_account(
        FIXTURE_IDS["ZAZU_FIXTURE_CREATED_BENEFICIARY_ID"],
        FIXTURE_IDS["ZAZU_FIXTURE_EXTERNAL_ACCOUNT_ID"],
    )
    assert response.body["id"] == FIXTURE_IDS["ZAZU_FIXTURE_EXTERNAL_ACCOUNT_ID"]
    assert "default" in response.body


def test_create_external_account(make_client):
    zazu = make_client(["beneficiaries/create_external_account"], body_match="exact")
    response = zazu.beneficiaries.create_external_account(
        FIXTURE_IDS["ZAZU_FIXTURE_CREATED_BENEFICIARY_ID"],
        account_number=FIXTURE_IDS["ZAZU_FIXTURE_NEW_ACCOUNT_NUMBER"],
        name="Fixture Secondary Account",
    )
    assert response.status == 201
    assert response.body["name"] == "Fixture Secondary Account"
    assert response.body["default"] is False
