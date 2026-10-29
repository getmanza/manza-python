"""Mirrors lib/manza/webhook.rb.

Verifies incoming webhook deliveries. Pure functions, no HTTP.

Every delivery carries ``X-Manza-Signature`` (hex HMAC-SHA256 of
``"<timestamp>.<raw body>"`` under the endpoint's signing secret) and
``X-Manza-Timestamp`` (Unix seconds, fresh on every attempt). The legacy
``X-Zazu-*`` names carry the same values.

Pass the **raw request body** (bytes or str), never re-serialized JSON::

    from manza import ManzaArgumentError, webhook

    try:
        event = webhook.construct_event(
            payload=request.get_data(), headers=request.headers, secret=signing_secret
        )
    except ManzaArgumentError:
        return "", 401
    event["event"]  # "payment.authorization_requested"
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Iterable
from typing import Any, Protocol

from .errors import ManzaArgumentError

DEFAULT_TOLERANCE = 300  # seconds

_TIMESTAMP = re.compile(r"[+-]?[0-9]+")


class Headers(Protocol):
    """Anything with ``items()``: a dict, a WSGI environ, Flask's or Starlette's
    headers, or ``http.server``'s ``self.headers``."""

    def items(self) -> Iterable[tuple[str, Any]]: ...


def sign(*, payload: str | bytes, timestamp: str | int, secret: str) -> str:
    """Hex HMAC-SHA256 of ``"<timestamp>.<payload>"``. For tests and local tools."""
    body = payload if isinstance(payload, bytes) else _utf8(str(payload))
    return hmac.new(_utf8(secret), _utf8(f"{timestamp}.") + body, hashlib.sha256).hexdigest()


def verify(
    *,
    payload: str | bytes,
    signature: str,
    timestamp: str | int,
    secret: str,
    tolerance: int | None = DEFAULT_TOLERANCE,
    now: float | None = None,
) -> bool:
    """True when the signature matches (constant time) and the timestamp is
    within ``tolerance`` seconds of ``now`` (Unix seconds, default the current
    time). ``tolerance=None`` skips the timestamp check (for replaying a captured
    delivery only). Never raises on bad input; returns False."""
    return _signature_matches(payload, signature, timestamp, secret) and _timestamp_fresh(
        timestamp, tolerance, now
    )


def construct_event(
    *,
    payload: str | bytes,
    headers: Headers,
    secret: str,
    tolerance: int | None = DEFAULT_TOLERANCE,
    now: float | None = None,
) -> dict[str, Any]:
    """Reads X-Manza-Signature / X-Manza-Timestamp from ``headers``
    (case-insensitive, X-Zazu-* fallback, WSGI ``HTTP_X_MANZA_*`` form too),
    verifies them, and returns the parsed JSON object. Raises
    ``ManzaArgumentError`` when a header is missing, the signature does not
    match, the timestamp is outside tolerance, or the body is not a JSON object.
    """
    normalized = _normalize_headers(headers)
    signature = _header(normalized, "signature")
    timestamp = _header(normalized, "timestamp")

    if not _signature_matches(payload, signature, timestamp, secret):
        raise ManzaArgumentError("invalid webhook signature")
    if not _timestamp_fresh(timestamp, tolerance, now):
        raise ManzaArgumentError("webhook timestamp outside tolerance")

    try:
        event = json.loads(payload)
    except ValueError as err:  # JSONDecodeError and UnicodeDecodeError
        raise ManzaArgumentError("webhook payload is not JSON") from err
    if not isinstance(event, dict):
        raise ManzaArgumentError("webhook payload is not a JSON object")
    return event


def _signature_matches(payload: Any, signature: Any, timestamp: Any, secret: Any) -> bool:
    if not isinstance(payload, str | bytes) or not isinstance(secret, str) or not secret:
        return False
    if not isinstance(signature, str) or _parse_timestamp(timestamp) is None:
        return False
    expected = sign(payload=payload, timestamp=timestamp, secret=secret)
    # compare_digest raises on a non-ASCII str; compare bytes so a junk header
    # is a mismatch, not an exception.
    return hmac.compare_digest(_utf8(expected), _utf8(signature))


def _utf8(text: str) -> bytes:
    # surrogatepass: a lone surrogate is a mismatch, never a UnicodeEncodeError.
    return text.encode("utf-8", "surrogatepass")


def _timestamp_fresh(timestamp: Any, tolerance: int | None, now: float | None) -> bool:
    if tolerance is None:
        return True
    seconds = _parse_timestamp(timestamp)
    current = time.time() if now is None else now
    return seconds is not None and abs(int(current) - seconds) <= tolerance


def _parse_timestamp(timestamp: Any) -> int | None:
    if isinstance(timestamp, bool):
        return None
    if isinstance(timestamp, int):
        return timestamp
    if isinstance(timestamp, str) and _TIMESTAMP.fullmatch(timestamp):
        try:
            return int(timestamp)
        except ValueError:  # past sys.get_int_max_str_digits()
            return None
    return None


def _normalize_headers(headers: Headers) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in headers.items():
        key = str(name)
        if key[:5].upper() == "HTTP_":
            key = key[5:]
        normalized[key.replace("_", "-").lower()] = value
    return normalized


def _header(normalized: dict[str, Any], suffix: str) -> str:
    value = normalized.get(f"x-manza-{suffix}")
    if value is None:
        value = normalized.get(f"x-zazu-{suffix}")
    if value is not None and str(value) != "":
        return str(value)
    raise ManzaArgumentError(f"missing X-Manza-{suffix.capitalize()} header")
