"""The example's .env loader."""

from __future__ import annotations

import os

import env_file


def test_strips_inline_comments_outside_quotes(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "# a comment\n"
        "PORT=4599 # local tunnel\n"
        'QUOTED="a # b" # trailing\n'
        "SINGLE='x#y'\n"
        "HASH_IN_VALUE=abc#def\n"
        "export EXPORTED=1\n"
    )
    for name in ("PORT", "QUOTED", "SINGLE", "HASH_IN_VALUE", "EXPORTED"):
        monkeypatch.delenv(name, raising=False)

    env_file.load(path)

    assert os.environ["PORT"] == "4599"
    assert os.environ["QUOTED"] == "a # b"
    assert os.environ["SINGLE"] == "x#y"
    assert os.environ["HASH_IN_VALUE"] == "abc#def"
    assert os.environ["EXPORTED"] == "1"
