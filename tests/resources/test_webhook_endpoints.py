"""Mirror of spec/manza/resources/webhook_endpoints_spec.rb."""

from __future__ import annotations

from manza import Page
from tests.fixture_ids import FIXTURE_IDS


def test_list(make_client):
    manza = make_client(["webhook_endpoints/list"])
    page = manza.webhook_endpoints.list()
    assert isinstance(page, Page)


def test_get(make_client):
    manza = make_client(["webhook_endpoints/get"])
    response = manza.webhook_endpoints.get(FIXTURE_IDS["MANZA_FIXTURE_WEBHOOK_ID"])
    assert isinstance(response.body["id"], str)


def test_create(make_client):
    manza = make_client(["webhook_endpoints/create"])
    response = manza.webhook_endpoints.create(
        url="https://example.com/zazu-webhooks",
        events=["payment_link.paid"],
        description="SDK fixture endpoint",
    )
    assert response.status == 201


def test_update(make_client):
    manza = make_client(["webhook_endpoints/update"])
    response = manza.webhook_endpoints.update(
        FIXTURE_IDS["MANZA_FIXTURE_WEBHOOK_ID"],
        description="Updated description",
        events=["payment_link.paid"],
    )
    assert response.success


def test_delete(make_client):
    manza = make_client(["webhook_endpoints/delete"])
    response = manza.webhook_endpoints.delete(FIXTURE_IDS["MANZA_FIXTURE_DELETABLE_WEBHOOK_ID"])
    assert response.status == 204


def test_test_endpoint(make_client):
    manza = make_client(["webhook_endpoints/test"])
    response = manza.webhook_endpoints.test_endpoint(FIXTURE_IDS["MANZA_FIXTURE_WEBHOOK_ID"])
    assert response.success


def test_regenerate_secret(make_client):
    manza = make_client(["webhook_endpoints/regenerate_secret"])
    response = manza.webhook_endpoints.regenerate_secret(FIXTURE_IDS["MANZA_FIXTURE_WEBHOOK_ID"])
    assert response.success


def test_enable(make_client):
    manza = make_client(["webhook_endpoints/enable"])
    response = manza.webhook_endpoints.enable(FIXTURE_IDS["MANZA_FIXTURE_DISABLED_WEBHOOK_ID"])
    assert response.success


def test_disable(make_client):
    manza = make_client(["webhook_endpoints/disable"])
    response = manza.webhook_endpoints.disable(FIXTURE_IDS["MANZA_FIXTURE_ENABLED_WEBHOOK_ID"])
    assert response.success
