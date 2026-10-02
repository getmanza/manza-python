"""Mirror of spec/manza/resources/entity_spec.rb."""

from __future__ import annotations


def test_entity_get(make_client):
    manza = make_client(["entity/get"])
    response = manza.entity.get()
    assert response.status == 200
    assert isinstance(response.body["id"], str)
