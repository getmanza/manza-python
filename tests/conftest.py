"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from manza import Manza

from .cassette_replay import BodyMatch, cassette_client
from .fixture_ids import REPLAY_BASE_URL, TEST_API_KEY


@pytest.fixture
def make_client() -> Iterator[Callable[[list[str]], Manza]]:
    """Return a factory: `make_client(["customers/list", ...])` builds a Manza
    bound to a cassette-replay transport that walks those cassettes in order.

    Load one cassette per test when two cassettes share method + URI
    (`transfer_drafts/authorize` vs `authorize_same_key`, `create` vs
    `create_duplicate`). `body_match` tightens matching: "exact" compares the
    recorded request body byte for byte, "without_signature" compares the
    parsed JSON minus its `signature` key."""

    clients: list[Manza] = []

    def _factory(cassettes: list[str], body_match: BodyMatch | None = None) -> Manza:
        http = cassette_client(cassettes, body_match)
        client = Manza(api_key=TEST_API_KEY, base_url=REPLAY_BASE_URL, http_client=http)
        clients.append(client)
        return client

    yield _factory

    for c in clients:
        c.close()
