"""Your own record of the transfers you created, keyed by the client_reference
you generated. A JSON file, so the creator (create_transfer.py) and the
authorizer (authorizer.py) can run as two processes. Swap it for your database
in production::

    {"po_8812": {"payment_id": "...", "amount": "2500.0",
                 "currency_code": "MAD", "account_id": "...",
                 "payee": "ext:..."}}

The lock uses ``fcntl``, so this file runs on macOS and Linux.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any


class Ledger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(
        self,
        client_reference: str,
        *,
        payment_id: str,
        amount: str,
        currency_code: str,
        account_id: str,
        payee: str,
    ) -> dict[str, str]:
        entry = {
            "payment_id": payment_id,
            "amount": amount,
            "currency_code": currency_code,
            "account_id": account_id,
            "payee": payee,
        }
        # Serialize writers on a separate lock file, write the new ledger to a
        # temporary file and rename it over the old one: a reader sees the old
        # or the new ledger, never a half-written one, and a crash mid-write
        # leaves the old ledger intact.
        lock_fd = os.open(f"{self._path}.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            entries = self._read_entries()
            entries[client_reference] = entry
            tmp = f"{self._path}.{os.getpid()}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(entries, f, indent=2)
            os.replace(tmp, self._path)
        finally:
            os.close(lock_fd)
        return entry

    def find(self, client_reference: str) -> dict[str, Any] | None:
        """The entry for ``client_reference``, or None."""
        entry = self._read_entries().get(client_reference)
        return entry if isinstance(entry, dict) else None

    def _read_entries(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        text = self._path.read_text()
        return json.loads(text) if text.strip() else {}
