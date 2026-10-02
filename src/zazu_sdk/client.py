"""Mirrors lib/zazu/client.rb. Sync HTTP entry point built on httpx."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

import httpx

from ._version import __version__
from .errors import (
    ZazuAuthenticationError,
    ZazuConfigurationError,
    ZazuConflictError,
    ZazuConnectionError,
    ZazuError,
    ZazuForbiddenError,
    ZazuNotFoundError,
    ZazuRateLimitError,
    ZazuServerError,
    ZazuValidationError,
)
from .page import MAX_PER_PAGE, Page
from .resources.accounts import Accounts
from .resources.beneficiaries import Beneficiaries
from .resources.checkout_sessions import CheckoutSessions
from .resources.customers import Customers
from .resources.entity import Entity
from .resources.invoices import Invoices
from .resources.payee_trust_requests import PayeeTrustRequests
from .resources.payment_links import PaymentLinks
from .resources.transfer_drafts import TransferDrafts
from .resources.webhook_endpoints import WebhookEndpoints
from .response import ZazuResponse

# Morocco production. South Africa is https://za.manza.finance.
DEFAULT_BASE_URL = "https://ma.manza.finance"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = f"zazu-sdk/{__version__}"


class Zazu:
    """Top-level Zazu client. Resources hang off it as attributes."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        api_version: str | None = None,
        timeout: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        api_key = api_key or os.getenv("ZAZU_API_KEY")
        if not api_key:
            raise ZazuConfigurationError(
                "Missing api_key. Pass api_key= or set ZAZU_API_KEY."
            )
        self.api_key = api_key
        self.base_url = (base_url or os.getenv("ZAZU_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_version = api_version or os.getenv("ZAZU_API_VERSION")
        self.timeout = (
            timeout if timeout is not None else _env_float("ZAZU_TIMEOUT", DEFAULT_TIMEOUT)
        )
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=self.timeout)

        self.accounts = Accounts(self)
        self.beneficiaries = Beneficiaries(self)
        self.checkout_sessions = CheckoutSessions(self)
        self.customers = Customers(self)
        self.entity = Entity(self)
        self.invoices = Invoices(self)
        self.payee_trust_requests = PayeeTrustRequests(self)
        self.payment_links = PaymentLinks(self)
        self.transfer_drafts = TransferDrafts(self)
        self.webhook_endpoints = WebhookEndpoints(self)

    def __enter__(self) -> Zazu:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> ZazuResponse:
        url = self._build_url(path, params)
        request_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if self.api_version:
            request_headers["Zazu-Version"] = self.api_version
        if headers:
            request_headers.update(headers)

        request_kwargs: dict[str, Any] = {"headers": request_headers}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            # Compact, raw UTF-8: byte-identical to zazu-ruby's JSON.generate.
            request_kwargs["content"] = json.dumps(
                body, separators=(",", ":"), ensure_ascii=False
            ).encode()

        try:
            raw = self._http.request(method.upper(), url, **request_kwargs)
        except httpx.TimeoutException as err:
            raise ZazuConnectionError(f"Request timed out after {self.timeout}s") from err
        except httpx.HTTPError as err:
            raise ZazuConnectionError(f"Connection failed: {err}") from err

        parsed = _parse_body(raw)
        response = ZazuResponse(raw, parsed)
        if response.success:
            return response
        raise _build_error(response)

    def _build_url(self, path: str, params: dict[str, Any] | None) -> str:
        trimmed = path.lstrip("/")
        url = f"{self.base_url}/{trimmed}"
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url = f"{url}?{urlencode(cleaned, doseq=True)}"
        return url


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_body(raw: httpx.Response) -> Any:
    content_type = raw.headers.get("content-type", "")
    if "json" not in content_type:
        return None
    text = raw.text
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _error_payload(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    err = body.get("error")
    return err if isinstance(err, dict) else {}


def _build_error(response: ZazuResponse) -> ZazuError:
    payload = _error_payload(response.body)
    message = payload.get("message")
    opts: dict[str, Any] = {
        "status": response.status,
        "request_id": response.request_id,
        "type": payload.get("type"),
        "param": payload.get("param"),
        "body": response.body,
        "headers": response.headers,
    }

    status = response.status
    if status == 401:
        return ZazuAuthenticationError(message or "Authentication failed", **opts)
    if status == 403:
        return ZazuForbiddenError(message or "Forbidden", **opts)
    if status == 404:
        return ZazuNotFoundError(message or "Not found", **opts)
    if status == 400:
        return ZazuValidationError(message or "Bad request", **opts)
    if status == 422:
        return ZazuValidationError(message or "Validation failed", **opts)
    if status == 409:
        return ZazuConflictError(
            message or "Conflict", payment_id=payload.get("payment_id"), **opts
        )
    if status == 429:
        retry_after = response.headers.get("retry-after")
        try:
            retry_after_int = int(retry_after) if retry_after else None
        except ValueError:
            retry_after_int = None
        return ZazuRateLimitError(
            message or "Rate limited", retry_after=retry_after_int, **opts
        )
    if 500 <= status < 600:
        return ZazuServerError(message or f"Server error ({status})", **opts)
    return ZazuError(message or f"Unexpected status {status}", **opts)


__all__ = ["MAX_PER_PAGE", "Page", "Zazu"]
