"""Environment lookup: `MANZA_<NAME>` first, then the legacy `ZAZU_<NAME>`.

The legacy name still works for all of 1.x and warns once per variable."""

from __future__ import annotations

import os
import threading
import warnings

_warned: set[str] = set()
_lock = threading.Lock()


def get(name: str) -> str | None:
    """Return `MANZA_<name>`, else `ZAZU_<name>` (warning once), else None."""
    value = os.getenv(f"MANZA_{name}")
    if value:
        return value
    legacy = f"ZAZU_{name}"
    value = os.getenv(legacy)
    if value:
        with _lock:
            first = legacy not in _warned
            _warned.add(legacy)
        if first:
            warnings.warn(
                f"{legacy} is deprecated; set MANZA_{name} instead. "
                "The ZAZU_* fallback will be removed in 2.0.",
                FutureWarning,
                stacklevel=3,
            )
        return value
    return None


def reset_warnings() -> None:
    """Forget which legacy variables already warned (for tests)."""
    _warned.clear()
