"""Mirrors lib/manza/errors.rb. Eleven-class hierarchy shared across SDKs."""

from __future__ import annotations

from typing import Any


class ManzaError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
        type: str | None = None,
        param: str | None = None,
        body: Any = None,
        headers: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id
        self.type = type
        self.param = param
        self.body = body
        self.headers = headers


class ManzaArgumentError(ManzaError):
    """Caller passed bad arguments before any HTTP request was made."""


class ManzaConfigurationError(ManzaError):
    """Missing or invalid client configuration (e.g. no API key)."""


class ManzaConnectionError(ManzaError):
    """The HTTP request failed before getting a response (timeout, DNS, refused)."""


class ManzaAuthenticationError(ManzaError):
    """HTTP 401."""


class ManzaForbiddenError(ManzaError):
    """HTTP 403."""


class ManzaNotFoundError(ManzaError):
    """HTTP 404."""


class ManzaValidationError(ManzaError):
    """HTTP 400 (malformed request, e.g. a bad `limit`/`cursor`) or 422 (rejected body).

    `param` carries the offending field name when the API supplies it.
    """


class ManzaPlanLimitReachedError(ManzaValidationError):
    """HTTP 422 with `type` "plan_limit_reached": the entity's plan caps this kind
    of record and the cap is reached. Retrying does not help until the plan
    changes or the period rolls over. `kind` names what is capped (e.g.
    "invoices"), `current` the count the entity holds and `max` the cap.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: str | None = None,
        current: int | None = None,
        max: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.kind = kind
        self.current = current
        self.max = max


class ManzaConflictError(ManzaError):
    """HTTP 409. The request conflicts with an existing resource.

    For a duplicate `client_reference` on a transfer draft (`type` is
    "duplicate_client_reference"), `payment_id` names the draft that already holds it.
    """

    def __init__(self, message: str, *, payment_id: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.payment_id = payment_id


class ManzaRateLimitError(ManzaError):
    """HTTP 429. `retry_after` is the value of the Retry-After header in seconds, if present."""

    def __init__(self, message: str, *, retry_after: int | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ManzaServerError(ManzaError):
    """HTTP 5xx."""
