"""Mirror of spec/examples/transfer_authorizer_spec.rb in manza-ruby.

Drives the example's authorizer with a signed copy of the documented
`payment.authorization_requested` payload. API calls go to an
`httpx.MockTransport`: no cassette, no network.
"""

from __future__ import annotations

import copy
import http.client
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from authorizer import App, make_handler
from ledger import Ledger

from manza import Manza, transfer_authorization, webhook

SECRET = "whsec_example_authorizer_secret"
BASE_URL = "https://staging.manza.example"
DRAFT_ID = "01958e51-7c5a-7000-8000-000000000012"
AUTHORIZATION_ID = "01958e51-7c5a-7000-8000-000000000011"
AUTHORIZE_PATH = f"/api/payments/{DRAFT_ID}/authorize"
DECLINE_PATH = f"/api/payments/{DRAFT_ID}/decline"
EXAMPLE_PAYLOAD: dict[str, Any] = {
    "event": "payment.authorization_requested",
    "event_id": "01958e51-7c5a-7000-8000-000000000010",
    "created_at": "2026-10-01T12:00:00Z",
    "data": {
        "authorization": {
            "id": AUTHORIZATION_ID,
            "nonce": "9f86d081884c7d659a2feaa0c55ad015",
            "expires_at": "2026-10-01T13:00:00Z",
            "signature_version": "manza.transfer-authorization.v1",
        },
        "payment": {
            "id": DRAFT_ID,
            "amount": "2500.0",
            "currency_code": "ZAR",
            "account_id": "01958e51-7c5a-7000-8000-000000000013",
            "payee": "ext:01958e51-7c5a-7000-8000-000000000014",
            "beneficiary_id": "01958e51-7c5a-7000-8000-000000000015",
            "external_account_id": "01958e51-7c5a-7000-8000-000000000014",
            "destination_account_id": None,
            "payment_reference": "INV-2026-001",
            "client_reference": "po_8812",
            "payee_trusted": False,
        },
        "signature_input": (
            "manza.transfer-authorization.v1|01958e51-7c5a-7000-8000-000000000012|"
            "9f86d081884c7d659a2feaa0c55ad015|2500.0|ZAR|01958e51-7c5a-7000-8000-000000000013|"
            "ext:01958e51-7c5a-7000-8000-000000000014|po_8812"
        ),
    },
}
LEDGER_ENTRY = {
    "payment_id": DRAFT_ID,
    "amount": "2500.0",
    "currency_code": "ZAR",
    "account_id": "01958e51-7c5a-7000-8000-000000000013",
    "payee": "ext:01958e51-7c5a-7000-8000-000000000014",
}


def json_response(status: int, body: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": "application/json", **(headers or {})},
        content=json.dumps(body).encode(),
    )


class FakeApi:
    """Answers each `(method, path)` with its queued responses in order (the last
    one repeats) and records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._routes: dict[tuple[str, str], list[httpx.Response]] = {}

    def on(self, method: str, path: str, *responses: httpx.Response) -> None:
        self._routes[(method, path)] = list(responses)

    def calls(self, path: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == path]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self._routes.get((request.method, request.url.path))
        if not queue:
            raise AssertionError(f"unexpected {request.method} {request.url}")
        return queue.pop(0) if len(queue) > 1 else queue[0]


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger.json")


@pytest.fixture
def log(caplog) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger="transfer_authorizer")
    return caplog


def build_app(api: FakeApi, ledger: Ledger, *, allow_new_payees: bool = True) -> App:
    client = Manza(
        api_key="key-b",
        base_url=BASE_URL,
        http_client=httpx.Client(transport=httpx.MockTransport(api)),
    )
    return App(
        client=client,
        secret=SECRET,
        ledger=ledger,
        executor=lambda job: job(),
        ledger_wait=0,
        retry_delay=0,
        allow_new_payees=allow_new_payees,
    )


def deliver(app: App, payload: Any, *, signature: str | None = None) -> int:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signature = signature or webhook.sign(payload=body, timestamp=timestamp, secret=SECRET)
    headers = {"X-Manza-Signature": signature, "X-Manza-Timestamp": timestamp}
    return app.handle(body, headers)


def payload_with(**payment: Any) -> dict[str, Any]:
    payload = copy.deepcopy(EXAMPLE_PAYLOAD)
    payload["data"]["payment"].update(payment)
    return payload


def expected_signature() -> str:
    signature_input = transfer_authorization.signature_input(
        **LEDGER_ENTRY, nonce="9f86d081884c7d659a2feaa0c55ad015", client_reference="po_8812"
    )
    return transfer_authorization.sign(SECRET, signature_input)


PROCESSING = json_response(200, {"id": DRAFT_ID, "status": "processing"})
DECLINED = json_response(200, {"id": AUTHORIZATION_ID, "status": "declined"})
UNAVAILABLE = json_response(503, {})


class TestWithAMatchingLedgerEntry:
    @pytest.fixture(autouse=True)
    def _record(self, ledger: Ledger) -> None:
        ledger.record("po_8812", **LEDGER_ENTRY)

    def test_signs_from_the_ledger_and_authorizes_with_key_b(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, PROCESSING)

        status = deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert status == 200
        [request] = api.calls(AUTHORIZE_PATH)
        assert request.headers["Authorization"] == "Bearer key-b"
        assert json.loads(request.content) == {
            "authorization_id": AUTHORIZATION_ID,
            "signature": expected_signature(),
        }
        for line in ("verified", "ledger match", "signed", "authorized"):
            assert line in log.text

    def test_logs_the_api_error_type_and_request_id_when_authorize_fails(self, api, ledger, log):
        api.on(
            "POST",
            AUTHORIZE_PATH,
            json_response(
                422,
                {"error": {"message": "Signature does not match", "type": "invalid_signature"}},
                {"X-Request-Id": "req_123"},
            ),
        )

        assert deliver(build_app(api, ledger), EXAMPLE_PAYLOAD) == 200
        assert "invalid_signature" in log.text
        assert "req_123" in log.text

    def test_does_not_authorize_when_the_webhooks_signature_input_differs(
        self, api, ledger, log
    ):
        payload = copy.deepcopy(EXAMPLE_PAYLOAD)
        payload["data"]["signature_input"] = "something-else"

        deliver(build_app(api, ledger), payload)

        assert api.requests == []
        assert "something-else" in log.text
        assert EXAMPLE_PAYLOAD["data"]["signature_input"] in log.text

    def test_retries_authorize_after_a_transient_failure(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, UNAVAILABLE, PROCESSING)

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert len(api.calls(AUTHORIZE_PATH)) == 2
        assert "retrying" in log.text
        assert "authorized payment" in log.text

    def test_gives_up_after_three_attempts(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, UNAVAILABLE)

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert len(api.calls(AUTHORIZE_PATH)) == 3
        assert "API error ManzaServerError" in log.text

    def test_retries_authorize_while_the_api_answers_authorization_busy(self, api, ledger, log):
        busy = json_response(409, {"error": {"type": "authorization_busy"}})
        api.on("POST", AUTHORIZE_PATH, busy, PROCESSING)

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert len(api.calls(AUTHORIZE_PATH)) == 2
        assert "retrying" in log.text
        assert "authorized payment" in log.text

    def test_does_not_retry_another_conflict(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, json_response(409, {"error": {"type": "already_answered"}}))

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert len(api.calls(AUTHORIZE_PATH)) == 1
        assert "API error ManzaConflictError" in log.text

    def test_does_not_retry_a_validation_error(self, api, ledger):
        api.on("POST", AUTHORIZE_PATH, json_response(422, {"error": {"type": "invalid_signature"}}))

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert len(api.calls(AUTHORIZE_PATH)) == 1

    def test_logs_that_a_new_payee_will_be_trusted_on_authorize(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, PROCESSING)

        deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

        assert (
            "new payee ext:01958e51-7c5a-7000-8000-000000000014, will be trusted on authorize"
            in log.text
        )

    def test_does_not_log_a_new_payee_when_the_payee_is_already_trusted(self, api, ledger, log):
        api.on("POST", AUTHORIZE_PATH, PROCESSING)

        deliver(build_app(api, ledger), payload_with(payee_trusted=True))

        assert "new payee" not in log.text


class TestWithAllowNewPayeesFalse:
    @pytest.fixture(autouse=True)
    def _record(self, ledger: Ledger) -> None:
        ledger.record("po_8812", **LEDGER_ENTRY)

    def test_declines_a_transfer_to_a_payee_that_is_not_trusted_yet(self, api, ledger, log):
        api.on("POST", DECLINE_PATH, DECLINED)

        deliver(build_app(api, ledger, allow_new_payees=False), EXAMPLE_PAYLOAD)

        [request] = api.calls(DECLINE_PATH)
        body = json.loads(request.content)
        assert body["authorization_id"] == AUTHORIZATION_ID
        assert "new payee" in body["reason"]
        assert api.calls(AUTHORIZE_PATH) == []
        assert "declined" in log.text

    def test_declines_a_webhook_that_does_not_say_whether_the_payee_is_trusted(
        self, api, ledger
    ):
        api.on("POST", DECLINE_PATH, json_response(200, {}))
        payload = copy.deepcopy(EXAMPLE_PAYLOAD)
        del payload["data"]["payment"]["payee_trusted"]

        deliver(build_app(api, ledger, allow_new_payees=False), payload)

        [request] = api.calls(DECLINE_PATH)
        assert "new payee" in json.loads(request.content)["reason"]

    def test_authorizes_a_trusted_payee(self, api, ledger):
        api.on("POST", AUTHORIZE_PATH, PROCESSING)

        deliver(build_app(api, ledger, allow_new_payees=False), payload_with(payee_trusted=True))

        assert len(api.calls(AUTHORIZE_PATH)) == 1


def test_a_ledger_mismatch_declines_with_a_reason_naming_the_field(api, ledger, log):
    ledger.record("po_8812", **{**LEDGER_ENTRY, "amount": "25000.0"})
    api.on("POST", DECLINE_PATH, DECLINED)

    status = deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

    assert status == 200
    [request] = api.calls(DECLINE_PATH)
    body = json.loads(request.content)
    assert body["authorization_id"] == AUTHORIZATION_ID
    assert "amount" in body["reason"]
    assert api.calls(AUTHORIZE_PATH) == []
    assert "declined" in log.text


def test_without_a_ledger_entry_declines_a_client_reference_never_issued(api, ledger):
    api.on("POST", DECLINE_PATH, json_response(200, {}))

    deliver(build_app(api, ledger), EXAMPLE_PAYLOAD)

    [request] = api.calls(DECLINE_PATH)
    assert "po_8812" in json.loads(request.content)["reason"]


def test_a_bad_signature_answers_401_and_calls_nothing(api, ledger, log):
    status = deliver(build_app(api, ledger), EXAMPLE_PAYLOAD, signature="0" * 64)

    assert status == 401
    assert api.requests == []
    assert "rejected a delivery: invalid webhook signature" in log.text


def test_a_signed_body_that_is_not_a_json_object_answers_401_and_calls_nothing(api, ledger):
    assert deliver(build_app(api, ledger), b"[]") == 401
    assert api.requests == []


def test_another_event_answers_200_and_calls_nothing(api, ledger, log):
    payload = {"event": "test.ping", "event_id": "0199a1b2-0000-7000-8000-000000000010"}

    assert deliver(build_app(api, ledger), payload) == 200
    assert api.requests == []
    assert "ignoring test.ping" in log.text


@pytest.fixture
def server(api: FakeApi, ledger: Ledger) -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(build_app(api, ledger)))
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def post(url: str, body: bytes, signature: str) -> tuple[int, bytes]:
    timestamp = str(int(time.time()))
    signature = signature or webhook.sign(payload=body, timestamp=timestamp, secret=SECRET)
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"X-Manza-Signature": signature, "X-Manza-Timestamp": timestamp},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        with err:
            return err.code, err.read()


def test_the_http_server_passes_the_raw_body_and_headers_to_the_app(server, api):
    body = json.dumps({"event": "test.ping"}).encode()

    assert post(server, body, "") == (200, b"ok")
    assert post(server, body, "0" * 64) == (401, b"unauthorized")
    assert api.requests == []


@pytest.mark.parametrize("length", ["lots", "-5", "-1", str(10**12), "9" * 20])
def test_the_http_server_answers_400_to_a_content_length_that_is_not_a_size(server, api, length):
    url = urlsplit(server)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    try:
        connection.putrequest("POST", "/")
        connection.putheader("Content-Length", length)
        connection.endheaders()
        response = connection.getresponse()
        assert (response.status, response.read()) == (400, b"bad request")
    finally:
        connection.close()
    assert api.requests == []
