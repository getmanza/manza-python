"""Mirror of spec/examples/preflight_spec.rb in manza-ruby.

Drives the example's preflight against `httpx.MockTransport` answers shaped like
the documented responses. No cassette, no network: each failure is a mocked
response.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from preflight import Preflight

BASE_URL = "https://staging.manza.example"
ACCOUNT_ID = "01958e51-7c5a-7000-8000-000000000013"
BENEFICIARY_ID = "01958e51-7c5a-7000-8000-000000000015"
ENDPOINT_ID = "01958e51-7c5a-7000-8000-000000000020"
NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)

Route = Callable[[], httpx.Response]


def json_response(status: int, body: Any) -> httpx.Response:
    return httpx.Response(
        status, headers={"content-type": "application/json"}, content=json.dumps(body).encode()
    )


def error(status: int, type: str) -> httpx.Response:
    return json_response(status, {"error": {"type": type, "message": "refused"}})


class Setup:
    """The documented responses of a complete setup, each one overridable."""

    def __init__(self) -> None:
        self.env = {
            "MANZA_BASE_URL": BASE_URL,
            "MANZA_CREATOR_API_KEY": "key-a",
            "MANZA_AUTHORIZER_API_KEY": "key-b",
            "MANZA_AUTHORIZER_SECRET": "whsec_example",
            "MANZA_ACCOUNT_ID": ACCOUNT_ID,
            "MANZA_BENEFICIARY_ID": BENEFICIARY_ID,
        }
        self.authorizer: dict[str, Any] = {
            "status": "active",
            "suspension_reason": None,
            "currency_code": "MAD",
            "per_transfer_limit": "1000.0",
            "daily_limit": "5000.0",
            "daily_authorized_total": "100.0",
            "secret_expires_at": "2027-01-18T00:00:00Z",
            "webhook_endpoint_id": ENDPOINT_ID,
            "enrolled_at": "2026-10-01T08:30:00Z",
        }
        self.endpoint = {
            "id": ENDPOINT_ID,
            "url": "https://authorizer.example.com/",
            "status": "active",
        }
        self.payee = {
            "id": "01958e51-7c5a-7000-8000-000000000014",
            "default": True,
            "trusted": True,
        }
        self.requests: list[httpx.Request] = []
        # (path, key) -> answer. Key A reads everything but the authorizer.
        self.routes: dict[tuple[str, str], Route] = {
            ("/api/entity", "key-a"): lambda: json_response(200, {"id": "e1", "name": "Acme"}),
            ("/api/transfer_authorizer", "key-b"): lambda: json_response(200, self.authorizer),
            (f"/api/accounts/{ACCOUNT_ID}", "key-a"): lambda: json_response(
                200, {"id": ACCOUNT_ID, "currency_code": "MAD"}
            ),
            (f"/api/webhook_endpoints/{ENDPOINT_ID}", "key-a"): lambda: json_response(
                200, self.endpoint
            ),
            (f"/api/beneficiaries/{BENEFICIARY_ID}", "key-a"): lambda: json_response(
                200, {"id": BENEFICIARY_ID, "external_accounts": [self.payee]}
            ),
        }

    def answer(self, path: str, key: str, response: httpx.Response) -> None:
        self.routes[(path, key)] = lambda: response

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = request.headers["Authorization"].removeprefix("Bearer ")
        route = self.routes.get((request.url.path, key))
        if request.method != "GET" or route is None:
            raise AssertionError(f"unexpected {request.method} {request.url} with {key}")
        return route()

    def run(self, amount: str = "10.00") -> tuple[bool, str]:
        out = io.StringIO()
        http = httpx.Client(transport=httpx.MockTransport(self))
        ok = Preflight(env=self.env, amount=amount, out=out, now=NOW, http_client=http).run()
        return ok, out.getvalue()


@pytest.fixture
def setup() -> Setup:
    return Setup()


def failures(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("✗")]


def warnings_of(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("!")]


def test_passes_every_step_when_the_setup_is_complete(setup):
    ok, output = setup.run()

    assert ok is True
    assert failures(output) == []
    assert len([line for line in output.splitlines() if line.startswith("✓")]) == 9


def test_fails_when_a_key_is_missing(setup):
    setup.env["MANZA_AUTHORIZER_API_KEY"] = ""
    ok, output = setup.run()

    assert ok is False
    assert "MANZA_AUTHORIZER_API_KEY" in failures(output)[0]
    assert setup.requests == []


def test_fails_when_the_account_or_beneficiary_id_is_missing(setup):
    setup.env["MANZA_BENEFICIARY_ID"] = ""
    ok, output = setup.run()

    assert ok is False
    assert "MANZA_BENEFICIARY_ID" in failures(output)[0]
    assert setup.requests == []


def test_fails_when_the_amount_is_not_a_decimal_and_runs_the_other_checks(setup):
    ok, output = setup.run(amount="ten")

    assert ok is False
    [failure] = failures(output)
    assert "'ten'" in failure
    assert "10.00" in failure
    assert "✓ transfer authorizer is active" in output
    assert "limit per transfer and" not in output


@pytest.mark.parametrize("amount", ["-5", "0", "1/2", "1e2", "\u0661\u0660"])
def test_fails_when_the_amount_is_not_positive(setup, amount):
    _, output = setup.run(amount=amount)

    assert repr(amount) in failures(output)[0]
    assert "positive" in failures(output)[0]


def test_stops_before_any_request_on_a_missing_key_even_with_a_bad_amount(setup):
    setup.env["MANZA_CREATOR_API_KEY"] = ""
    _, output = setup.run(amount="0")

    assert len(failures(output)) == 2
    assert setup.requests == []


def test_fails_when_both_keys_are_the_same(setup):
    setup.env["MANZA_AUTHORIZER_API_KEY"] = "key-a"
    _, output = setup.run()

    assert "different" in failures(output)[0]


def test_fails_when_key_a_cannot_reach_the_entity(setup):
    setup.answer("/api/entity", "key-a", error(401, "authentication_error"))
    _, output = setup.run()

    assert "key A" in failures(output)[0]
    assert "MANZA_CREATOR_API_KEY" in failures(output)[0]


def test_fails_when_no_authorizer_is_enrolled(setup):
    setup.answer("/api/transfer_authorizer", "key-b", error(404, "not_found_error"))
    _, output = setup.run()

    assert "no transfer authorizer is enrolled" in failures(output)[0]
    assert "Transfer approval" in failures(output)[0]


def test_fails_when_key_b_cannot_read_the_authorizer(setup):
    setup.answer("/api/transfer_authorizer", "key-b", error(403, "insufficient_scope"))
    _, output = setup.run()

    for part in ("key B", "insufficient_scope", "transfers:authorize"):
        assert part in failures(output)[0]


def test_fails_when_key_a_cannot_read_the_account(setup):
    setup.answer(f"/api/accounts/{ACCOUNT_ID}", "key-a", error(403, "insufficient_scope"))
    _, output = setup.run()

    assert "key A" in failures(output)[0]
    assert "accounts:read" in failures(output)[0]


def test_fails_when_key_a_cannot_read_the_enrolled_webhook_endpoint(setup):
    setup.answer(f"/api/webhook_endpoints/{ENDPOINT_ID}", "key-a", error(403, "insufficient_scope"))
    _, output = setup.run()

    assert "key A" in failures(output)[0]
    assert "webhook_endpoints:read" in failures(output)[0]


def test_fails_when_key_a_cannot_read_the_beneficiary(setup):
    setup.answer(f"/api/beneficiaries/{BENEFICIARY_ID}", "key-a", error(404, "not_found_error"))
    _, output = setup.run()

    assert "key A" in failures(output)[0]
    assert "MANZA_BENEFICIARY_ID" in failures(output)[0]


def test_fails_once_on_the_authorizer_line_when_the_secret_has_expired(setup):
    setup.authorizer.update(
        status="suspended",
        suspension_reason="secret_expired",
        secret_expires_at="2026-10-19T00:00:00Z",
    )
    _, output = setup.run()

    [failure] = failures(output)
    assert "suspended (secret_expired)" in failure
    assert "rotates the secret" in failure


def test_fails_when_the_enrolled_webhook_endpoint_was_deleted(setup):
    setup.answer(f"/api/webhook_endpoints/{ENDPOINT_ID}", "key-a", error(404, "not_found_error"))
    _, output = setup.run()

    assert "was deleted" in failures(output)[0]
    assert "enrol" in failures(output)[0]


def test_fails_with_the_suspension_reason_and_its_fix(setup):
    setup.authorizer.update(status="suspended", suspension_reason="endpoint_disabled")
    _, output = setup.run()

    assert "suspended (endpoint_disabled)" in failures(output)[0]
    assert "re-enable" in failures(output)[0]


def test_fails_when_the_accounts_currency_is_not_the_enrolled_one(setup):
    setup.answer(
        f"/api/accounts/{ACCOUNT_ID}",
        "key-a",
        json_response(200, {"id": ACCOUNT_ID, "currency_code": "ZAR"}),
    )
    _, output = setup.run()

    assert "ZAR" in failures(output)[0]
    assert "MAD" in failures(output)[0]


def test_fails_when_the_secret_expires_within_7_days(setup):
    setup.authorizer["secret_expires_at"] = "2026-10-23T00:00:00Z"
    _, output = setup.run()

    assert "secret expires" in failures(output)[0]
    assert "rotate" in failures(output)[0]


def test_fails_when_the_signing_secret_is_not_set(setup):
    setup.env["MANZA_AUTHORIZER_SECRET"] = ""
    _, output = setup.run()

    assert "MANZA_AUTHORIZER_SECRET" in failures(output)[0]


def test_fails_when_the_enrolled_webhook_endpoint_is_disabled(setup):
    setup.endpoint["status"] = "disabled"
    _, output = setup.run()

    for part in ("disabled", "enable", "if the authorizer stays suspended"):
        assert part in failures(output)[0]


def test_warns_when_the_endpoint_is_on_a_url_that_changes_when_the_tunnel_restarts(setup):
    setup.endpoint["url"] = "https://abc123.ngrok-free.app/"
    ok, output = setup.run()

    assert ok is True
    assert "ngrok-free.app" in warnings_of(output)[0]
    assert "reserved domain" in warnings_of(output)[0]


def test_fails_when_the_amount_is_over_the_limit_per_transfer(setup):
    _, output = setup.run(amount="1500.00")

    assert "limit per transfer" in failures(output)[0]


def test_fails_when_the_amount_does_not_fit_in_the_last_24_hours_room(setup):
    setup.authorizer["daily_authorized_total"] = "4995.0"
    _, output = setup.run()

    assert "24 hours" in failures(output)[0]


def test_warns_that_a_new_payee_needs_the_toggle_which_the_api_does_not_show(setup):
    setup.payee["trusted"] = False
    ok, output = setup.run()

    assert ok is True
    for part in ("not trusted yet", "Approve transfers to new payees", "IP allowlist"):
        assert part in warnings_of(output)[0]


def test_fails_when_the_beneficiary_has_no_default_bank_account(setup):
    setup.payee["default"] = False
    _, output = setup.run()

    assert "default bank account" in failures(output)[0]
