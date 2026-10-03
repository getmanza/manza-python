"""Mirrors lib/manza/resources/entity.rb."""

from __future__ import annotations

from ..response import ManzaResponse
from .base import ResourceBase


class Entity(ResourceBase):
    def get(self) -> ManzaResponse:
        return self.http_get("api/entity")
