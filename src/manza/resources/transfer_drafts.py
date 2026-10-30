"""Mirrors lib/manza/resources/transfer_drafts.rb.

Deprecated: use ``Payments`` (``manza.payments``). Kept for all of 1.x; it is
the same class and calls ``/api/payments``.
"""

from __future__ import annotations

from .payments import Payments

TransferDrafts = Payments
