"""Makes examples/transfer_authorizer importable: its scripts import their
siblings (`from ledger import Ledger`) the way `python authorizer.py` does."""

from __future__ import annotations

import sys
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "transfer_authorizer"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))
