"""Mirrors lib/manza/resources/transfer_drafts.rb.

Deprecated: use ``Payments`` (``manza.payments``). Kept in 1.x and 2.0; it is
the same class and calls ``/api/payments``.
"""

from __future__ import annotations

from .payments import Payments

TransferDrafts = Payments
