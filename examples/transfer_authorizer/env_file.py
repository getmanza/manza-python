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
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key.strip()] = value
