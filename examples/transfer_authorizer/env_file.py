"""Loads ``.env`` next to these scripts into ``os.environ``, overriding what the
shell exported (like Ruby's ``Dotenv.overload``). Standard library only."""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path = HERE / ".env") -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        os.environ[key.strip()] = _value(value.strip())


def _value(raw: str) -> str:
    """A quoted value runs to its closing quote; an unquoted one stops at " #"."""
    if raw[:1] in ("\"", "'"):
        end = raw.find(raw[0], 1)
        if end > 0:
            return raw[1:end]
    return raw.split(" #", 1)[0].rstrip()
