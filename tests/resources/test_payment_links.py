"""Mirror of spec/manza/resources/payment_links_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["payment_links/list"])
    page = manza.payment_links.list()
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["payment_links/get"])
    response = manza.payment_links.get(FIXTURE_IDS["MANZA_FIXTURE_PAYMENT_LINK_ID"])
    assert isinstance(response.body["id"], str)


def test_create(make_client):
    manza = make_client(["payment_links/create"])
    response = manza.payment_links.create(
        account_id=FIXTURE_IDS["MANZA_FIXTURE_ACCOUNT_ID"],
        amount="100.00",
        title="SDK fixture",
        description="Created by manza-ruby fixture spec",
        link_type="single",
    )
    assert response.status == 201


def test_cancel(make_client):
    manza = make_client(["payment_links/cancel"])
    response = manza.payment_links.cancel(FIXTURE_IDS["MANZA_FIXTURE_CANCELLABLE_PAYMENT_LINK_ID"])
    assert response.success
