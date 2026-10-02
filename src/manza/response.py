"""Mirrors lib/manza/response.rb."""

from __future__ import annotations

from typing import Any

import httpx


class ManzaResponse:
    """Thin wrapper over httpx.Response — exposes status, headers, and parsed body."""

    def __init__(self, raw: httpx.Response, body: Any) -> None:
        self._raw = raw
        self.status: int = raw.status_code
        self.headers: httpx.Headers = raw.headers
        self.body: Any = body

    @property
    def request_id(self) -> str | None:
        value = self.headers.get("X-Request-Id")
        return value if isinstance(value, str) else None

    @property
    def success(self) -> bool:
        return 200 <= self.status < 300
