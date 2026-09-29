# zazu-python

Python SDK for the Zazu API. **Cassette consumer** — replays cassettes
recorded by [`zazu-ruby`](https://github.com/getzazu/zazu-ruby) (the canonical
SDK that records against `staging.zazu.ma`).

## Stack

| Concern | Tool | Notes |
|---|---|---|
| Language | Python ≥ 3.11 (matrix: 3.11, 3.12, 3.13) | `pyproject.toml` `requires-python` |
| HTTP | httpx (sync) | `src/zazu_sdk/client.py` |
| Tests | pytest | `tests/` |
| Cassettes | Custom YAML reader → `httpx.MockTransport` | `tests/cassette_replay.py` |
| Lint | ruff | `pyproject.toml` `[tool.ruff]` |
| Types | mypy strict | `[tool.mypy]` |
| Build | hatchling | `pyproject.toml` `[build-system]` |
| Publish | PyPI **OIDC trusted publishing** | `.github/workflows/release.yml` |

## Public API surface

```python
from zazu_sdk import Zazu

zazu = Zazu(api_key="sk_live_...")

zazu.entity.get()
zazu.accounts.list(currency_code="MAD")
zazu.accounts.list_transactions(account_id)
zazu.customers.list(q="Acme")
zazu.customers.create(...)
zazu.invoices.list()
zazu.payment_links.cancel(id)
zazu.webhook_endpoints.list()
zazu.checkout_sessions.create(...)
```

- `Page[T]` — cursor-based pagination, hard cap of 100/page (`MAX_PER_PAGE`)
- 9-class `ZazuError` hierarchy — discriminate via `isinstance(err, ZazuValidationError)`, never status-code matching
- Snake-case wire format — request/response bodies are returned as-is

## How to work in this codebase

1. **Tests come first.** Every change to `src/` ships with a test. The cassette-replay tests are the cross-language contract.
2. **Use the SDK's primitives.** `Page`, `ZazuError` subclasses, the `ResourceBase.http_get/post/patch/delete` helpers, `encode_path` for URL construction. Don't hand-roll `httpx` calls.
3. **Snake-case stays.** Response keys are wire-format. We don't camelCase them.
4. **`ruff check` and `mypy` clean.** CI gates on both. Don't add `# noqa` to silence — fix the issue.

## Critical rules

- **Cassettes come from `zazu-ruby`'s release tarball.** `python scripts/fetch_cassettes.py` downloads `cassettes-vX.Y.Z.tar.gz` from the latest non-draft `getzazu/zazu-ruby` release. Cassettes are git-ignored.
- **Cassette replay is request-shape-strict.** The matcher compares method + scheme + host + path + sorted query params. Body match is loose (msw-style); the bytes must still parse, but JSON key order doesn't matter.
- **No long-lived PyPI API token.** Releases publish via OIDC trusted publishing through the `pypi` GitHub environment. Verify the binding on https://pypi.org/manage/account/publishing/ if it ever drifts.
- **Ruby is the canonical surface.** New resources or methods are added to `zazu-ruby` first (which records the cassettes), then mirrored here. Don't add a method that has no cassette to back it.
- **No new error classes without updating other SDKs.** The 9-class hierarchy is shared across SDKs.

## Development workflow

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_cassettes.py

# Daily loop
pytest tests/resources/test_customers.py    # while iterating
pytest                                      # full suite
ruff check                                  # lint
mypy                                        # types

# Release (after PR merge)
# 1. Bump src/zazu_sdk/_version.py
# 2. Add CHANGELOG.md entry
# 3. git tag vX.Y.Z && git push --tags
#    The release.yml workflow handles PyPI publish via OIDC.
```

## Cross-SDK contract

| SDK | Repo |
|---|---|
| Ruby (canonical) | https://github.com/getzazu/zazu-ruby |
| TypeScript | https://github.com/getzazu/zazu-ts |
| Python (this) | https://github.com/getzazu/zazu-python |
| Go | https://github.com/getzazu/zazu-go (planned) |
| Rust | https://github.com/getzazu/zazu-rust (planned) |
| CLI | https://github.com/getzazu/cli |

If the contract breaks (e.g. new request shape), it's a coordinated change across at least zazu-ruby and every SDK that consumes the cassette tarball.

## Models

Sessions run on `opus` (Opus 5.5) with `fable` (Fable 5.1) as the advisor (`.claude/settings.json`). Fable is spent where judgment matters most: ask for a plan on Fable (a `fable` subagent or `/model fable`); plan mode itself runs on Opus and asks the advisor. The advisor is consulted at decision points (before choosing an approach, a schema or public API, a migration, a dependency, anything irreversible, and when a failure repeats). Run the `fable-validator` agent on a finished implementation before its pull request opens (no command in this repo runs it for you). Agents pin their tier by alias, never by full model ID: `fable` for plans and validation; `opus` for orchestration, security, full PR review, payments and production debugging; `sonnet` for the implementation specialists and TDD; `haiku` for mechanical scans. Every spawned agent names its `model:`; a subagent whose definition names no model runs on `sonnet` (`CLAUDE_CODE_SUBAGENT_MODEL`), never on the session's model.
