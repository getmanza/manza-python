# zazu-python

Python SDK for the Zazu API (PyPI: `zazu-sdk`, import package `zazu_sdk`). **Cassette consumer**: it replays the cassettes that [`zazu-ruby`](https://github.com/getmanza/zazu-ruby) records, and zazu-ruby is the reference implementation of the SDK family. Every new resource or method lands in zazu-ruby first, then is mirrored here.

## Stack

| Concern | Tool | Notes |
|---|---|---|
| Language | Python >= 3.11 (CI matrix: 3.11, 3.12, 3.13) | `pyproject.toml` `requires-python`, `.github/workflows/ci.yml` |
| HTTP | httpx (sync) | `src/zazu_sdk/client.py` |
| Tests | pytest (`filterwarnings = error`) | `tests/` |
| Replay harness | Custom VCR-YAML reader -> `httpx.MockTransport` | `tests/cassette_replay.py`, `tests/conftest.py` (`make_client`) |
| Lint | ruff | `[tool.ruff]` in `pyproject.toml` |
| Types | mypy strict | `[tool.mypy]`, checks `src/zazu_sdk` only |
| Build | hatchling | `pyproject.toml` `[build-system]` |
| Registry | PyPI `zazu-sdk` | OIDC trusted publishing, GitHub environment `pypi` |
| Release | `bin/release` | zazu SDK release kit; repo-specific bits in `scripts/version` + `scripts/release-check` |

## Public API surface

```python
from zazu_sdk import Zazu, ZazuConflictError, transfer_authorization as ta

zazu = Zazu(api_key="sk_live_...")   # or ZAZU_API_KEY; base_url= or ZAZU_BASE_URL

zazu.entity.get()
zazu.accounts.list(currency_code="MAD")
zazu.accounts.list_transactions(account_id)
zazu.customers.list(q="Acme")
zazu.customers.create(...)
zazu.invoices.list()
zazu.payment_links.cancel(id)
zazu.webhook_endpoints.list()
zazu.checkout_sessions.create(...)

# Beneficiaries and external accounts
zazu.beneficiaries.create(...)
zazu.beneficiaries.list_external_accounts(beneficiary_id)
zazu.beneficiaries.get_external_account(beneficiary_id, id)
zazu.beneficiaries.create_external_account(beneficiary_id, ...)

# Payee trust requests
zazu.payee_trust_requests.create([external_account_id])
zazu.payee_trust_requests.get(id)

# Machine-authorized transfer drafts
try:
    draft = zazu.transfer_drafts.create(..., client_reference="ref-1")
except ZazuConflictError as err:      # 409 duplicate client_reference
    existing = err.payment_id
signature = ta.sign(secret, ta.signature_input(...))   # built from YOUR record of the transfer
zazu.transfer_drafts.authorize(id, authorization_id, signature)
zazu.transfer_drafts.decline(id, authorization_id, reason="...")
```

- `Page` (generic `Page[T]`) is cursor-based with a hard cap of 100 per page (`MAX_PER_PAGE`); `auto_paging_iter()` chases cursors.
- Error model: a 10-class `ZazuError` hierarchy (`ZazuArgumentError`, `ZazuConfigurationError`, `ZazuConnectionError`, `ZazuAuthenticationError`, `ZazuForbiddenError`, `ZazuNotFoundError`, `ZazuValidationError`, `ZazuConflictError`, `ZazuRateLimitError`, `ZazuServerError`). Discriminate via `isinstance(err, ZazuValidationError)`, never status-code matching. 400 and 422 map to `ZazuValidationError`; 409 maps to `ZazuConflictError`, which carries `payment_id` for a duplicate transfer-draft `client_reference`.
- `transfer_drafts.authorize` raises `ZazuArgumentError` locally on a blank signature (before any HTTP call), because the API counts it as a failed attempt.
- `zazu_sdk.transfer_authorization` (`signature_input`, `sign`, `payee_for`) is the HMAC-SHA256 signer for authorization challenges. Pure functions, no HTTP.
- Snake-case wire format: request and response bodies are returned as-is. **No auto-camelCasing.**

## How to work in this codebase

1. **Tests come first.** Every change to `src/` ships with a test. Cassette-replay tests are the contract: they enforce the same wire format across Ruby, TS, Python and future SDKs.
2. **Use the SDK's primitives.** `Page`, `ZazuError` subclasses, the `ResourceBase.http_get/post/patch/delete` and `list_page` helpers, `ResourceBase.encode_path` for URL construction, `make_client` and the `FIXTURE_IDS` dict from `tests/fixture_ids.py` in tests. Don't hand-roll `httpx` calls or f-string URLs.
3. **Snake-case stays.** Response keys are wire format. We don't camelCase them.
4. **`ruff check` and `mypy` must be clean.** CI gates on both. Don't add `# noqa` or `# type: ignore` to silence them: fix the issue.

## Critical rules

- **Never call a live Zazu/Manza API** from tests, scripts or Claude sessions. Tests replay zazu-ruby's cassettes only. Live staging calls create real transfers and approval requests for the team. Only zazu-ruby records cassettes.
- **Cassettes come from zazu-ruby's newest `v*` release.** `python scripts/fetch_cassettes.py` downloads `cassettes-vX.Y.Z.tar.gz` (newest tag via `git ls-remote`, or pass a tag) into `tests/fixtures/cassettes/`, which is git-ignored.
- **Cassette contract.**
  - Cassettes are recorded against `https://ma.manza.dev` (`REPLAY_BASE_URL` in `tests/fixture_ids.py`).
  - Load one cassette per test: `transfer_drafts/authorize` vs `authorize_same_key`, and `create` vs `create_duplicate`, share method + URI, so loading both makes the wrong one match.
  - The matcher always compares method + scheme + host + path + sorted query params. Body matching is off by default and opt-in per test via `make_client([...], body_match=...)`: `"exact"` compares the recorded body byte for byte (request bodies are serialized compactly in recorded key order, like Ruby's `JSON.generate`); `"without_signature"` compares parsed JSON minus its `signature` key. The three authorize cassettes (`authorize`, `authorize_same_key`, `authorize_bad_signature`) use `"without_signature"`; the transfer-draft create/decline, beneficiary and payee-trust-request cassettes use `"exact"`.
  - Cassette responses carry no `Content-Length`.
  - `tests/fixture_ids.py` must stay identical to zazu-ruby's `spec/support/fixture_ids.rb` (29 entries). Placeholders must equal what VCR scrubbed the real IDs to.
- **Hosts.** Default `https://ma.manza.finance`; South Africa `https://za.manza.finance`; staging and cassettes `https://ma.manza.dev`. Env var names stay `ZAZU_*` and the namespace stays `Zazu` / `zazu_sdk` until the rename plan (zazu-ruby `docs/plans/2026-10-manza-rename.md`).
- **Error model is shared across the SDK family.** Adding an error class means coordinating zazu-ruby and zazu-ts at minimum. The 10th class is the conflict (409).
- **Signer.** `transfer_authorization` must keep reproducing the two fixed vectors from zazu-ruby's `spec/zazu/transfer_authorization_spec.rb` (mirrored in `tests/test_transfer_authorization.py`). Never sign the server's `signature_input` blindly: build it from your own record of the transfer.
- **Release.** `bin/release` is byte-identical across the SDK repos and is never edited in place. Repo-specific logic lives in `scripts/version` (reads/writes `src/zazu_sdk/_version.py`) and `scripts/release-check` (install, fetch cassettes, ruff, mypy, pytest). `release.yml` gates on tag == package version. Publishing uses PyPI **OIDC trusted publishing** (no long-lived token) through the GitHub environment `pypi`; the PyPI trusted-publisher binding must name `getmanza/zazu-python`, workflow `release.yml`, environment `pypi`. Verify at https://pypi.org/manage/project/zazu-sdk/settings/publishing/ if it ever drifts.
- **The repo moved from `getzazu` to `getmanza`.** Remotes and URLs must say `getmanza`.
- **Ruby is the canonical surface.** Don't add a method that has no cassette to back it.
- **Snake-case wire format.** Don't transform request/response bodies.
- **Never escape backticks in PR bodies.** With `<<'EOF'` (single-quoted heredoc) the shell passes everything through verbatim. See "PR descriptions" below.


## PR descriptions

Write PR description bodies in plain Markdown. **Do not escape backticks** with `` \` `` — GitHub renders `` \` `` literally as a backslash followed by a backtick, producing output like `` \`Page\` `` instead of the monospace `Page` the reader expects.

The usual cause is writing the description inside a bash heredoc (`gh pr create --body "$(cat <<'EOF' ... EOF)"`) and then reflexively escaping every backtick because of shell-quoting muscle memory. With `<<'EOF'` (single-quoted delimiter) the shell does NOT interpret anything inside the heredoc — backticks, dollars, and backslashes all pass through verbatim. So write them exactly as you want them rendered:

```bash
# Good — renders as `Page` in monospace
gh pr create --body "$(cat <<'EOF'
Uses the `Page` helper.
EOF
)"

# Bad — renders as \`Page\` literally in the PR body
gh pr create --body "$(cat <<'EOF'
Uses the \`Page\` helper.
EOF
)"
```

Same rule for code blocks — write triple-backticks unescaped. The single-quoted heredoc delimiter is doing all the shell-escaping work. If you find yourself typing `` \` `` inside a PR body, stop and remove the backslash.

## Striving for excellence

These are the Karpathy guidelines we apply on every change. They reduce common LLM coding mistakes.

### 1. Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Senior engineer test: would they call this overcomplicated?

### 3. Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that *your* changes orphaned. Don't remove pre-existing dead code unless asked.

### 4. Goal-driven execution

Define success criteria. Loop until verified.

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan with verification at each step.

## Development workflow

Mirrors `.github/workflows/ci.yml`.

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_cassettes.py      # downloads zazu-ruby's cassette tarball (no Zazu API call)

# Daily loop
pytest tests/resources/test_customers.py    # while iterating
pytest                                      # full suite
ruff check                                  # lint
mypy                                        # types (strict, src/zazu_sdk)

# Release (after PR merge, from a clean, up-to-date main)
bin/release list        # last releases + what patch/minor/major would give
bin/release --dry-run   # version + changes since the last tag, publishes nothing
bin/release minor       # or patch (default), major, an explicit 0.4.0; --force re-creates
# -> bumps src/zazu_sdk/_version.py, runs scripts/release-check, pushes main, publishes the GH release
# -> release.yml publishes to PyPI via OIDC
```

## Models

Sessions run on `opus` (Opus 5.5) with `fable` (Fable 5.1) as the advisor (`.claude/settings.json`). Fable is spent where judgment matters most: plans are written on Fable, the advisor is consulted at decision points (before choosing an approach, a schema or public API, a migration, a dependency, anything irreversible, and when a failure repeats), and the `fable-validator` agent checks every finished implementation before its pull request opens (`/lfg`, Phase 6.5). Commands pin their tier by alias, never by full model ID: `opus` for orchestration, security, full PR review, payments and production debugging; `sonnet` for the implementation specialists and TDD; `haiku` for mechanical scans. Every spawned agent names its `model:`; one that does not runs on `sonnet` (`CLAUDE_CODE_SUBAGENT_MODEL`), never on the session's model. Plan mode cannot take a model of its own: it runs on Opus and asks the advisor.

## Slash commands

These live in `.claude/commands/` and are available in any Claude Code session:

| Command | When |
|---|---|
| `/lfg <issue or feature>` | Full autonomous workflow with TDD + verification |
| `/github-review-pr <PR#>` | Full PR review pass: failures first, then comments |
| `/github-review-failures <PR#>` | Just fix CI failures on a PR |
| `/github-review-comments <PR#>` | Just respond to reviewer comments on a PR |
| `/coderabbit-review <PR#>` | Specifically address CodeRabbit findings (verify, fix valid, push back on stale/wrong) |

## Cross-SDK contract

`zazu-ruby` is the reference implementation:

- Records cassettes against `https://ma.manza.dev`
- Ships them as a release tarball (`cassettes-vX.Y.Z.tar.gz`) on each version
- All other SDKs (`zazu-ts`, this repo, and the planned `zazu-go`, `zazu-rust`, ...) replay these cassettes in their own test harness

If the contract breaks (e.g. a new request shape), it's a coordinated change across at least zazu-ruby and every SDK that consumes the tarball.

## Repository links

- Ruby SDK (reference): https://github.com/getmanza/zazu-ruby
- TypeScript SDK: https://github.com/getmanza/zazu-ts
- This repo: https://github.com/getmanza/zazu-python
- PyPI package: https://pypi.org/project/zazu-sdk/
- CLI consumer: https://github.com/getmanza/cli
