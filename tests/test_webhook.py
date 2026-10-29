"""Fixed test vector, shared by every SDK in the family (see
spec/manza/webhook_spec.rb in manza-ruby). Each SDK's verifier must accept
exactly this delivery. The signature was computed independently with:

    printf '%s' '1767225600.<payload>' | openssl dgst -sha256 -hmac 'whsec_test_vector_secret'
"""

from __future__ import annotations

from email.message import Message
from typing import Any

import pytest

from manza import ManzaArgumentError, webhook

SECRET = "whsec_test_vector_secret"
TIMESTAMP = "1767225600"
PAYLOAD = '{"event":"test.ping","event_id":"0199a1b2-0000-7000-8000-000000000010"}'
SIGNATURE = "970fdd13680015f73dbd172884498c6fd1e07d5b5c41aae081272598607fea75"
NOW = 1_767_225_600


# sign


def test_sign_signs_the_shared_vector():
    assert webhook.sign(payload=PAYLOAD, timestamp=TIMESTAMP, secret=SECRET) == SIGNATURE


def test_sign_accepts_an_int_timestamp():
    assert webhook.sign(payload=PAYLOAD, timestamp=NOW, secret=SECRET) == SIGNATURE


def test_sign_accepts_a_bytes_payload():
    assert webhook.sign(payload=PAYLOAD.encode(), timestamp=TIMESTAMP, secret=SECRET) == SIGNATURE


# verify


def verify(**overrides: Any) -> bool:
    kwargs: dict[str, Any] = {
        "payload": PAYLOAD,
        "signature": SIGNATURE,
        "timestamp": TIMESTAMP,
        "secret": SECRET,
        "now": NOW,
        **overrides,
    }
    return webhook.verify(**kwargs)


def test_verify_accepts_the_shared_vector():
    assert verify() is True


def test_verify_accepts_a_bytes_payload():
    assert verify(payload=PAYLOAD.encode()) is True


def test_verify_accepts_an_int_timestamp():
    assert verify(timestamp=NOW) is True


def test_verify_rejects_a_wrong_secret():
    assert verify(secret="whsec_other") is False


def test_verify_rejects_a_tampered_payload():
    assert verify(payload=PAYLOAD.replace("ping", "pong")) is False


def test_verify_rejects_a_signature_of_the_wrong_length_without_raising():
    assert verify(signature="abc") is False


def test_verify_rejects_a_non_ascii_signature_without_raising():
    assert verify(signature="é" * 64) is False


@pytest.mark.parametrize("field", ["signature", "payload", "secret"])
def test_verify_rejects_a_lone_surrogate_without_raising(field):
    assert verify(**{field: "\ud800" * 64}) is False


def test_verify_rejects_a_timestamp_301_seconds_old():
    assert verify(now=NOW + 301) is False


def test_verify_rejects_a_timestamp_301_seconds_in_the_future():
    assert verify(now=NOW - 301) is False


def test_verify_accepts_a_timestamp_exactly_at_the_tolerance():
    assert verify(now=NOW + 300) is True


def test_verify_skips_the_timestamp_check_with_tolerance_none():
    assert verify(now=NOW + 86_400, tolerance=None) is True


def test_verify_rejects_a_non_numeric_timestamp():
    assert verify(timestamp="yesterday", tolerance=None) is False


def test_verify_rejects_a_bool_timestamp():
    assert verify(timestamp=True, tolerance=None) is False


@pytest.mark.parametrize("field", ["signature", "timestamp", "payload", "secret"])
def test_verify_rejects_none_inputs(field):
    assert verify(**{field: None}) is False


def test_verify_rejects_an_empty_secret_even_with_a_signature_made_under_it():
    forged = webhook.sign(payload=PAYLOAD, timestamp=TIMESTAMP, secret="")
    assert verify(secret="", signature=forged) is False


def test_verify_rejects_a_non_string_payload():
    forged = signed_headers(42)["X-Manza-Signature"]
    assert verify(payload=42, signature=forged) is False


# construct_event


def construct(headers: Any, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "payload": PAYLOAD,
        "headers": headers,
        "secret": SECRET,
        "now": NOW,
        **overrides,
    }
    return webhook.construct_event(**kwargs)


def signed_headers(body: Any) -> dict[str, str]:
    return {
        "X-Manza-Signature": webhook.sign(payload=body, timestamp=TIMESTAMP, secret=SECRET),
        "X-Manza-Timestamp": TIMESTAMP,
    }


def test_construct_event_returns_the_parsed_event_for_x_manza_headers():
    event = construct({"X-Manza-Signature": SIGNATURE, "X-Manza-Timestamp": TIMESTAMP})
    assert event == {"event": "test.ping", "event_id": "0199a1b2-0000-7000-8000-000000000010"}


def test_construct_event_accepts_a_bytes_payload():
    headers = {"X-Manza-Signature": SIGNATURE, "X-Manza-Timestamp": TIMESTAMP}
    assert construct(headers, payload=PAYLOAD.encode())["event"] == "test.ping"


def test_construct_event_reads_mixed_case_header_names():
    headers = {"x-MANZA-signature": SIGNATURE, "X-manza-Timestamp": TIMESTAMP}
    assert construct(headers)["event"] == "test.ping"


def test_construct_event_reads_the_wsgi_environ_form():
    headers = {"HTTP_X_MANZA_SIGNATURE": SIGNATURE, "HTTP_X_MANZA_TIMESTAMP": TIMESTAMP}
    assert construct(headers)["event"] == "test.ping"


def test_construct_event_reads_http_server_headers():
    headers = Message()
    headers["X-Manza-Signature"] = SIGNATURE
    headers["X-Manza-Timestamp"] = TIMESTAMP
    assert construct(headers)["event"] == "test.ping"


def test_construct_event_falls_back_to_x_zazu_headers():
    headers = {"X-Zazu-Signature": SIGNATURE, "X-Zazu-Timestamp": TIMESTAMP}
    assert construct(headers)["event"] == "test.ping"


def test_construct_event_prefers_x_manza_over_x_zazu():
    headers = {
        "X-Manza-Signature": SIGNATURE,
        "X-Manza-Timestamp": TIMESTAMP,
        "X-Zazu-Signature": "0" * 64,
        "X-Zazu-Timestamp": "1",
    }
    assert construct(headers)["event"] == "test.ping"


def test_construct_event_raises_on_a_missing_signature_header():
    with pytest.raises(ManzaArgumentError, match=r"^missing X-Manza-Signature header$"):
        construct({"X-Manza-Timestamp": TIMESTAMP})


def test_construct_event_raises_on_a_missing_timestamp_header():
    with pytest.raises(ManzaArgumentError, match=r"^missing X-Manza-Timestamp header$"):
        construct({"X-Manza-Signature": SIGNATURE})


def test_construct_event_raises_on_a_bad_signature():
    with pytest.raises(ManzaArgumentError, match=r"^invalid webhook signature$"):
        construct({"X-Manza-Signature": "0" * 64, "X-Manza-Timestamp": TIMESTAMP})


def test_construct_event_raises_on_a_stale_timestamp():
    with pytest.raises(ManzaArgumentError, match=r"^webhook timestamp outside tolerance$"):
        construct(
            {"X-Manza-Signature": SIGNATURE, "X-Manza-Timestamp": TIMESTAMP}, now=NOW + 301
        )


def test_construct_event_accepts_a_stale_timestamp_with_tolerance_none():
    event = construct(
        {"X-Manza-Signature": SIGNATURE, "X-Manza-Timestamp": TIMESTAMP},
        now=NOW + 301,
        tolerance=None,
    )
    assert event["event"] == "test.ping"


def test_construct_event_raises_on_a_body_that_is_not_json():
    body = "not json"
    with pytest.raises(ManzaArgumentError, match=r"^webhook payload is not JSON$"):
        construct(signed_headers(body), payload=body)


def test_construct_event_raises_on_a_signed_body_that_is_not_utf8():
    body = b"\xff\xfe"
    with pytest.raises(ManzaArgumentError, match=r"^webhook payload is not JSON$"):
        construct(signed_headers(body), payload=body)


def test_construct_event_raises_argument_error_not_type_error_on_a_non_string_payload():
    with pytest.raises(ManzaArgumentError, match=r"^invalid webhook signature$"):
        construct(signed_headers(42), payload=42)


def test_construct_event_raises_on_an_empty_secret():
    headers = {
        "X-Manza-Signature": webhook.sign(payload=PAYLOAD, timestamp=TIMESTAMP, secret=""),
        "X-Manza-Timestamp": TIMESTAMP,
    }
    with pytest.raises(ManzaArgumentError, match=r"^invalid webhook signature$"):
        construct(headers, secret="")


@pytest.mark.parametrize("body", ["[]", "null", "42"])
def test_construct_event_raises_on_valid_json_that_is_not_an_object(body):
    with pytest.raises(ManzaArgumentError, match=r"^webhook payload is not a JSON object$"):
        construct(signed_headers(body), payload=body)
