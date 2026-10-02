"""Mirror of spec/manza/resources/accounts_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["accounts/list"])
    page = manza.accounts.list()
    assert isinstance(page, Page)


def test_list_currency_filtered(make_client):
    manza = make_client(["accounts/list_currency_filtered"])
    page = manza.accounts.list(currency_code="MAD")
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["accounts/get"])
    response = manza.accounts.get(FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"])
    assert isinstance(response.body["id"], str)


def test_list_transactions(make_client):
    manza = make_client(["accounts/list_transactions"])
    page = manza.accounts.list_transactions(FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"])
    assert isinstance(page, Page)


def test_get_transaction(make_client):
    manza = make_client(["accounts/get_transaction"])
    response = manza.accounts.get_transaction(
        FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
        FIXTURE_IDS["MANZA_FIXTURE_TRANSACTION_ID"],
    )
    assert isinstance(response.body["id"], str)
