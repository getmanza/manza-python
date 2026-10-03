"""MANZA_* env lookup with a one-time-warning ZAZU_* fallback."""

from __future__ import annotations

import warnings

import httpx
import pytest

from manza import Manza, ManzaConfigurationError, _env
from manza._version import __version__

ENV_NAMES = [
    "API_KEY",
    "BASE_URL",
    "API_VERSION",
    "TIMEOUT",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for suffix in ENV_NAMES:
        monkeypatch.delenv(f"MANZA_{suffix}", raising=False)
        monkeypatch.delenv(f"ZAZU_{suffix}", raising=False)
    _env.reset_warnings()
    yield
    _env.reset_warnings()


def _build(**kwargs) -> Manza:
    return Manza(http_client=httpx.Client(transport=httpx.MockTransport(lambda r: None)), **kwargs)


def test_manza_env_vars_are_read_without_warning(monkeypatch):
    monkeypatch.setenv("MANZA_API_KEY", "sk_manza")
    monkeypatch.setenv("MANZA_BASE_URL", "https://ma.manza.dev/")
    monkeypatch.setenv("MANZA_API_VERSION", "2026-01-01")
    monkeypatch.setenv("MANZA_TIMEOUT", "12.5")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client = _build()
    assert client.api_key == "sk_manza"
    assert client.base_url == "https://ma.manza.dev"
    assert client.api_version == "2026-01-01"
    assert client.timeout == 12.5


@pytest.mark.parametrize(
    ("suffix", "value", "attr", "expected"),
    [
        ("API_KEY", "sk_legacy", "api_key", "sk_legacy"),
        ("BASE_URL", "https://legacy.example", "base_url", "https://legacy.example"),
        ("API_VERSION", "2025-12-01", "api_version", "2025-12-01"),
        ("TIMEOUT", "7", "timeout", 7.0),
    ],
)
def test_zazu_env_falls_back_with_deprecation_warning(monkeypatch, suffix, value, attr, expected):
    if suffix != "API_KEY":
        monkeypatch.setenv("MANZA_API_KEY", "sk_manza")
    monkeypatch.setenv(f"ZAZU_{suffix}", value)
    with pytest.warns(FutureWarning, match=f"ZAZU_{suffix}.*MANZA_{suffix}"):
        client = _build()
    assert getattr(client, attr) == expected


def test_manza_wins_over_zazu_without_warning(monkeypatch):
    monkeypatch.setenv("MANZA_API_KEY", "sk_new")
    monkeypatch.setenv("ZAZU_API_KEY", "sk_old")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client = _build()
    assert client.api_key == "sk_new"


def test_fallback_warns_only_once_per_variable(monkeypatch):
    monkeypatch.setenv("ZAZU_API_KEY", "sk_legacy")
    with pytest.warns(FutureWarning):
        _build()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _build()
        _build()


def test_each_legacy_variable_warns_separately(monkeypatch):
    monkeypatch.setenv("ZAZU_API_KEY", "sk_legacy")
    monkeypatch.setenv("ZAZU_BASE_URL", "https://legacy.example")
    with pytest.warns(FutureWarning) as record:
        _build()
    messages = [str(w.message) for w in record]
    assert any("ZAZU_API_KEY" in m for m in messages)
    assert any("ZAZU_BASE_URL" in m for m in messages)


def test_explicit_arguments_skip_env_and_warning(monkeypatch):
    monkeypatch.setenv("ZAZU_API_KEY", "sk_legacy")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client = _build(api_key="sk_explicit", base_url="https://x.test", timeout=3.0)
    assert client.api_key == "sk_explicit"


def test_missing_key_error_names_manza_env(monkeypatch):
    with pytest.raises(ManzaConfigurationError, match="MANZA_API_KEY"):
        Manza()


def test_user_agent_and_version_header():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"{}")

    client = Manza(
        api_key="k",
        api_version="2026-01-01",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.request("GET", "/entity")
    assert seen["manza-version"] == "2026-01-01"
    assert "zazu-version" not in seen
    assert seen["user-agent"] == f"manza-python/{__version__}"
