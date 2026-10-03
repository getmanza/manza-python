"""Client wiring + error mapping."""

from __future__ import annotations

import httpx
import pytest

from manza import (
    Manza,
    ManzaAuthenticationError,
    ManzaConfigurationError,
    ManzaConflictError,
    ManzaConnectionError,
    ManzaForbiddenError,
    ManzaNotFoundError,
    ManzaRateLimitError,
    ManzaServerError,
    ManzaValidationError,
)


def test_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("MANZA_API_KEY", raising=False)
    monkeypatch.delenv("ZAZU_API_KEY", raising=False)
    with pytest.raises(ManzaConfigurationError):
        Manza()


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("MANZA_API_KEY", "sk_env_test")
    client = Manza()
    try:
        assert client.api_key == "sk_env_test"
    finally:
        client.close()


def test_base_url_default():
    client = Manza(api_key="sk_test")
    try:
        assert client.base_url == "https://ma.manza.finance"
    finally:
        client.close()


def test_base_url_strips_trailing_slash():
    client = Manza(api_key="sk_test", base_url="https://ma.manza.dev/")
    try:
        assert client.base_url == "https://ma.manza.dev"
    finally:
        client.close()


def _client_with_response(
    status: int,
    *,
    body: bytes = b"",
    content_type: str = "application/json",
    headers: dict | None = None,
) -> Manza:
    extra_headers = {"content-type": content_type, **(headers or {})}

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=extra_headers, content=body)

    return Manza(
        api_key="sk_test",
        base_url="https://api.manza.example",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (401, ManzaAuthenticationError),
        (403, ManzaForbiddenError),
        (404, ManzaNotFoundError),
        (400, ManzaValidationError),
        (409, ManzaConflictError),
        (422, ManzaValidationError),
        (500, ManzaServerError),
        (503, ManzaServerError),
    ],
)
def test_status_to_error_class(status, exc):
    client = _client_with_response(
        status, body=b'{"error":{"message":"nope"}}'
    )
    try:
        with pytest.raises(exc) as info:
            client.entity.get()
        assert info.value.status == status
        assert info.value.message == "nope"
    finally:
        client.close()


def test_conflict_error_exposes_payment_id():
    client = _client_with_response(
        409,
        body=(
            b'{"error":{"type":"duplicate_client_reference","message":"dup",'
            b'"payment_id":"draft-1"}}'
        ),
    )
    try:
        with pytest.raises(ManzaConflictError) as info:
            client.entity.get()
        assert info.value.payment_id == "draft-1"
        assert info.value.type == "duplicate_client_reference"
    finally:
        client.close()


def test_conflict_error_payment_id_defaults_to_none():
    client = _client_with_response(409, body=b'{"error":{"message":"nope"}}')
    try:
        with pytest.raises(ManzaConflictError) as info:
            client.entity.get()
        assert info.value.payment_id is None
    finally:
        client.close()


def test_rate_limit_parses_retry_after():
    client = _client_with_response(
        429,
        body=b'{"error":{"message":"slow down"}}',
        headers={"retry-after": "42"},
    )
    try:
        with pytest.raises(ManzaRateLimitError) as info:
            client.entity.get()
        assert info.value.retry_after == 42
    finally:
        client.close()


def test_connection_failure_wraps_as_connection_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = Manza(
        api_key="sk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(ManzaConnectionError):
            client.entity.get()
    finally:
        client.close()


def test_request_body_is_compact_utf8_json():
    # Matches Ruby's JSON.generate byte for byte, so exact-body cassettes
    # recorded by manza-ruby replay here: no spaces, raw UTF-8, no \u escapes.
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(201, headers={"content-type": "application/json"}, content=b"{}")

    manza = Manza(
        api_key="sk_test",
        base_url="https://ma.manza.dev",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    manza.beneficiaries.create(company_name="Société Générale", beneficiary_type="business")

    assert seen == ['{"company_name":"Société Générale","beneficiary_type":"business"}'.encode()]
