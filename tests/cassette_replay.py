"""Reads VCR YAML cassettes (recorded by manza-ruby) and registers them as
`httpx.MockTransport` handlers so identical interactions replay against this
SDK. The contract is enforced cross-language: every SDK that consumes this
tarball must replay the exact request shape. Method, URI and sorted query always
match; request bodies match only when a test opts in via `body_match`."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

import httpx
import yaml

BodyMatch = Literal["exact", "without_signature"]

CASSETTE_DIR = Path(__file__).parent / "fixtures" / "cassettes"


class _BinaryLoader(yaml.SafeLoader):
    """Ruby's Psych emits non-UTF-8 response bodies as `!binary | <base64>`,
    using a YAML primary tag rather than the canonical `tag:yaml.org,2002:binary`.
    Register both forms; decode to a UTF-8 string since Manza only returns JSON."""


def _construct_binary(loader: yaml.Loader, node: yaml.Node) -> str:
    raw = loader.construct_scalar(node)  # type: ignore[arg-type]
    return base64.b64decode("".join(raw.split())).decode("utf-8")


_BinaryLoader.add_constructor("!binary", _construct_binary)
_BinaryLoader.add_constructor("tag:yaml.org,2002:binary", _construct_binary)


def _load_cassette(name: str) -> list[dict[str, Any]]:
    path = CASSETTE_DIR / f"{name}.yml"
    with path.open() as f:
        data = yaml.load(f, Loader=_BinaryLoader)
    return list(data.get("http_interactions") or [])


def _sorted_query(qs: str) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted(parse_qsl(qs, keep_blank_values=True)))


def _without_signature(body: str) -> Any:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(parsed, dict):
        return {k: v for k, v in parsed.items() if k != "signature"}
    return parsed


def _body_matches(
    interaction: dict[str, Any], request: httpx.Request, body_match: BodyMatch | None
) -> bool:
    if body_match is None:
        return True
    recorded = (interaction["request"].get("body") or {}).get("string") or ""
    replayed = request.content.decode("utf-8")
    if body_match == "exact":
        return bool(recorded == replayed)
    return bool(_without_signature(recorded) == _without_signature(replayed))


def _interaction_matches(
    interaction: dict[str, Any], request: httpx.Request, body_match: BodyMatch | None = None
) -> bool:
    rec = interaction["request"]
    if rec["method"].upper() != request.method.upper():
        return False
    rec_url = urlsplit(rec["uri"])
    req_url = urlsplit(str(request.url))
    if (rec_url.scheme, rec_url.netloc, rec_url.path) != (
        req_url.scheme,
        req_url.netloc,
        req_url.path,
    ):
        return False
    if _sorted_query(rec_url.query) != _sorted_query(req_url.query):
        return False
    return _body_matches(interaction, request, body_match)


def _build_response(interaction: dict[str, Any]) -> httpx.Response:
    resp = interaction["response"]
    status = int(resp["status"]["code"])
    body_field = resp.get("body") or {}
    body_str = body_field.get("string", "") if isinstance(body_field, dict) else ""
    headers: list[tuple[str, str]] = []
    for k, v in (resp.get("headers") or {}).items():
        if isinstance(v, list):
            for item in v:
                headers.append((k, str(item)))
        else:
            headers.append((k, str(v)))
    return httpx.Response(status, headers=headers, content=body_str.encode("utf-8"))


class CassetteTransport:
    """An httpx.MockTransport handler that replays recorded interactions in order."""

    def __init__(self, cassette_names: list[str], body_match: BodyMatch | None = None) -> None:
        self._body_match = body_match
        interactions: list[dict[str, Any]] = []
        for name in cassette_names:
            interactions.extend(_load_cassette(name))
        self._remaining = interactions

    def __call__(self, request: httpx.Request) -> httpx.Response:
        for i, interaction in enumerate(self._remaining):
            if _interaction_matches(interaction, request, self._body_match):
                self._remaining.pop(i)
                return _build_response(interaction)
        raise AssertionError(
            f"No cassette interaction matched {request.method} {request.url}"
        )


def cassette_client(
    cassette_names: list[str], body_match: BodyMatch | None = None
) -> httpx.Client:
    transport = CassetteTransport(cassette_names, body_match)
    return httpx.Client(transport=httpx.MockTransport(transport))
