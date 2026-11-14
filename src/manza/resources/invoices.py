"""Mirrors lib/manza/resources/invoices.rb."""

from __future__ import annotations

from typing import Any

from ..page import MAX_PER_PAGE, Page
from ..response import ManzaResponse
from .base import ResourceBase


class Invoices(ResourceBase):
    def list(
        self,
        *,
        status: str | None = None,
        customer_id: str | None = None,
        limit: int = MAX_PER_PAGE,
        cursor: str | None = None,
    ) -> Page[Any]:
        """GET /api/invoices

        ``status``: draft, pending_approval, declined, approved, sent, paid,
        overdue or cancelled.
        """
        return self.list_page(
            "api/invoices",
            {"status": status, "customer_id": customer_id},
            limit=limit,
            cursor=cursor,
        )

    def get(self, id: str) -> ManzaResponse:
        return self.http_get(self.encode_path("api/invoices", id))

    def create(self, **attributes: Any) -> ManzaResponse:
        """POST /api/invoices

        Required: customer_id, account_id (the entity's account the invoice is
        paid into, from ``accounts.list``; without one the API answers 422
        ``state_error``, and an account that is not the entity's 422 with
        ``param`` "account_id"), issue_date, due_date and items. Optional:
        currency_code, reference, notes, payment_terms, send_to_email,
        discounts, delivery_date (MA only) and generate_payment_link.

        ``generate_payment_link=True`` asks for a card payment link, made from
        the invoice's account when the invoice is approved; it needs the
        ``payment_links:write`` scope and is taken only while payment links are
        enabled for the entity. A boolean, None (no link) or the strings
        "true", "false", "1" and "0" are taken; any other value raises
        ``ManzaValidationError`` (400) and nothing is created. It replaces the
        removed ``create_payment_link``.

        The response carries ``generate_payment_link``, the embedded
        ``account`` (``id``, ``name``, ``currency_code``, and ``rib`` in Morocco
        or ``account_number`` in South Africa) and ``payment_link`` once one
        exists. A plan that caps invoices raises ``ManzaPlanLimitReachedError``.
        """
        return self.http_post("api/invoices", body=attributes)

    def update(self, id: str, **attributes: Any) -> ManzaResponse:
        """PATCH /api/invoices/:id

        Takes the create fields, account_id and generate_payment_link included
        (the same scope and entity rule apply), on an invoice that is still
        editable.
        """
        return self.http_patch(self.encode_path("api/invoices", id), body=attributes)

    def send_invoice(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/invoices", id, "send"))

    def mark_as_paid(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/invoices", id, "mark_as_paid"))

    def cancel(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/invoices", id, "cancel"))

    def credit_note(self, id: str) -> ManzaResponse:
        return self.http_post(self.encode_path("api/invoices", id, "credit_note"))

    def delete(self, id: str) -> ManzaResponse:
        """DELETE /api/invoices/:id

        Only a ``draft``, ``pending_approval`` or ``declined`` invoice that has
        no number yet; any other raises ``ManzaValidationError``
        (``state_error``).
        """
        return self.http_delete(self.encode_path("api/invoices", id))
