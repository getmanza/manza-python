"""Mirrors lib/manza/resources/webhook_endpoints.rb."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class WebhookEndpoints(ResourceBase):
    def list(
        self,
        *,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        return self.list_page("api/webhook_endpoints", {}, limit=limit, cursor=cursor)

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/webhook_endpoints", id))

    def create(
        self,
        *,
        url: str,
        events: Sequence[str],
        description: str | None = None,
    ) -> ManzaResponse:
        body: dict[str, Any] = {"url": url, "events": list(events)}
        if description is not None:
            body["description"] = description
        return self.http_post("api/webhook_endpoints", body=body)

    def update(self, id: str, **attributes: Any) -> ManzaResponse:
        return self.http_patch(self.encode_path("api/webhook_endpoints", id), body=attributes)

    def delete(self, id: str) -> ManzaResponse:
        return self.http_delete(self.encode_path("api/webhook_endpoints", id))

    def test_endpoint(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/webhook_endpoints", id, "test"))

    def regenerate_secret(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/webhook_endpoints", id, "regenerate_secret"))

    def enable(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/webhook_endpoints", id, "enable"))

    def disable(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/webhook_endpoints", id, "disable"))
