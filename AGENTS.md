# manza-python

Python SDK for the Manza API (PyPI: `manza`, import package `manza`). **Cassette consumer**: it replays the cassettes that [`manza-ruby`](https://github.com/getmanza/manza-ruby) records, and manza-ruby is the reference implementation of the SDK family. Every new resource or method lands in manza-ruby first, then is mirrored here.

## Stack

| Concern | Tool | Notes |
|---|---|---|
| Language | Python >= 3.11 (CI matrix: 3.11, 3.12, 3.13) | `pyproject.toml` `requires-python`, `.github/workflows/ci.yml` |
| HTTP | httpx (sync) | `src/manza/client.py` |
| Tests | pytest (`filterwarnings = error`) | `tests/` |
| Replay harness | Custom VCR-YAML reader -> `httpx.MockTransport` | `tests/cassette_replay.py`, `tests/conftest.py` (`make_client`) |
| Lint | ruff | `[tool.ruff]` in `pyproject.toml` |
| Types | mypy strict | `[tool.mypy]`, checks `src/manza` only |
| Build | hatchling | `pyproject.toml` `[build-system]` |
| Registry | PyPI `manza` | OIDC trusted publishing, GitHub environment `pypi` |
| Release | `bin/release` | manza SDK release kit; repo-specific bits in `scripts/version` + `scripts/release-check` |

## Public API surface

```python
from manza import Manza, ManzaConflictError, transfer_authorization as ta, webhook

manza = Manza(api_key="sk_live_...")   # or MANZA_API_KEY; base_url= or MANZA_BASE_URL

manza.entity.get()
manza.accounts.list(currency_code="MAD")
manza.accounts.list_transactions(account_id)
manza.customers.list(q="Acme")
manza.customers.create(...)
manza.invoices.list()
manza.payment_links.cancel(id)
manza.webhook_endpoints.list()
manza.checkout_sessions.create(...)

# Beneficiaries and external accounts
manza.beneficiaries.create(...)
manza.beneficiaries.list_external_accounts(beneficiary_id)
manza.beneficiaries.get_external_account(beneficiary_id, id)
manza.beneficiaries.create_external_account(beneficiary_id, ...)

# Payee trust requests
manza.payee_trust_requests.create([external_account_id])
manza.payee_trust_requests.get(id)

# Machine-authorized payments (formerly transfer drafts)
try:
    draft = manza.payments.create(..., client_reference="ref-1")
except ManzaConflictError as err:      # 409 duplicate client_reference
    existing = err.payment_id
manza.payments.get(id)                 # authorization: status, refusal_reason
event = webhook.construct_event(payload=raw_body, headers=headers, secret=secret)
signature = ta.sign(secret, ta.signature_input(...))   # built from YOUR record of the transfer
manza.payments.authorize(id, authorization_id, signature)
manza.payments.decline(id, authorization_id, reason="...")
manza.transfer_authorizer.get()        # status, suspension_reason, limits; 404: none enrolled
# manza.transfer_drafts: deprecated alias of manza.payments (DeprecationWarning), all of 1.x
```

- `Page` (generic `Page[T]`) is cursor-based with a hard cap of 100 per page (`MAX_PER_PAGE`); `auto_paging_iter()` chases cursors.
- Error model: a 10-class `ManzaError` hierarchy (`ManzaArgumentError`, `ManzaConfigurationError`, `ManzaConnectionError`, `ManzaAuthenticationError`, `ManzaForbiddenError`, `ManzaNotFoundError`, `ManzaValidationError`, `ManzaConflictError`, `ManzaRateLimitError`, `ManzaServerError`). Discriminate via `isinstance(err, ManzaValidationError)`, never status-code matching. 400 and 422 map to `ManzaValidationError`; 409 maps to `ManzaConflictError`, which carries `payment_id` for a duplicate transfer-draft `client_reference`.
- `payments.authorize` raises `ManzaArgumentError` locally on a blank signature (before any HTTP call), because the API counts it as a failed attempt.
- `manza.transfer_authorization` (`signature_input`, `sign`, `payee_for`) is the HMAC-SHA256 signer for authorization challenges. Pure functions, no HTTP.
- `manza.webhook` (`verify`, `construct_event`, `sign`) checks `X-Manza-Signature` deliveries, tested with the fixed vector shared across SDKs. `verify` returns `False` on any bad delivery and never raises; `construct_event` raises the existing `ManzaArgumentError` (no new error class).
- `examples/transfer_authorizer/` is a runnable authorizer on `http.server` (standard library only), tested in `tests/examples/` with `httpx.MockTransport`. It is not in the published package (`[tool.hatch.build]` ships `src/manza` only).
- Snake-case wire format: request and response bodies are returned as-is. **No auto-camelCasing.**

## How to work in this codebase

1. **Tests come first.** Every change to `src/` ships with a test. Cassette-replay tests are the contract: they enforce the same wire format across Ruby, TS, Python and future SDKs.
2. **Use the SDK's primitives.** `Page`, `ManzaError` subclasses, the `ResourceBase.http_get/post/patch/delete` and `list_page` helpers, `ResourceBase.encode_path` for URL construction, `make_client` and the `FIXTURE_IDS` dict from `tests/fixture_ids.py` in tests. Don't hand-roll `httpx` calls or f-string URLs.
3. **Snake-case stays.** Response keys are wire format. We don't camelCase them.
4. **`ruff check` and `mypy` must be clean.** CI gates on both. Don't add `# noqa` or `# type: ignore` to silence them: fix the issue.

## Critical rules

- **Never call a live Manza API** from tests, scripts or Claude sessions. Tests replay manza-ruby's cassettes only. Live staging calls create real transfers and approval requests for the team. Only manza-ruby records cassettes.
- **Cassettes come from the manza-ruby release pinned in `PINNED_TAG`** (currently `v1.3.0`; bump it deliberately). `python scripts/fetch_cassettes.py` downloads `cassettes-vX.Y.Z.tar.gz` (the pinned tag, or pass a tag) into `tests/fixtures/cassettes/`, which is git-ignored.
- **Cassette contract.**
  - Cassettes are recorded against `https://ma.manza.dev` (`REPLAY_BASE_URL` in `tests/fixture_ids.py`).
  - Load one cassette per test: `payments/authorize` vs `authorize_same_key`, and `create` vs `create_duplicate`, share method + URI, so loading both makes the wrong one match.
  - The matcher always compares method + scheme + host + path + sorted query params. Body matching is off by default and opt-in per test via `make_client([...], body_match=...)`: `"exact"` compares the recorded body byte for byte (request bodies are serialized compactly in recorded key order, like Ruby's `JSON.generate`); `"without_signature"` compares parsed JSON minus its `signature` key. The four authorize cassettes (`payments/authorize`, `authorize_same_key`, `authorize_bad_signature`, `authorize_new_payee`) use `"without_signature"`; the payment create/decline, beneficiary and payee-trust-request cassettes use `"exact"`.
  - Cassette responses carry no `Content-Length`.
  - `tests/fixture_ids.py` must stay identical to manza-ruby's `spec/support/fixture_ids.rb` (34 entries). Placeholders must equal what VCR scrubbed the real IDs to.
- **Replay mismatch** (`No cassette interaction matched ...`): load one cassette per test, refetch stale cassettes (`python scripts/fetch_cassettes.py`), check path, query and host (`https://ma.manza.dev`) and, for body-matched tests, the compact recorded-order body. Fix the SDK, never the cassette; a genuinely new request shape is re-recorded in manza-ruby and released first.
- **Public API break** is made only on purpose, named in the changelog and released as a major version.
- **Hosts.** Default `https://ma.manza.finance`; South Africa `https://za.manza.finance`; staging and cassettes `https://ma.manza.dev`.
- **Error model is shared across the SDK family.** Adding an error class means coordinating manza-ruby and manza-ts at minimum. `ManzaConflictError` handles 409 responses.
- **Signer.** `transfer_authorization` must keep reproducing the two fixed vectors from manza-ruby's `spec/manza/transfer_authorization_spec.rb` (mirrored in `tests/test_transfer_authorization.py`). Never sign the server's `signature_input` blindly: build it from your own record of the transfer.
- **Release.** `bin/release` is byte-identical across the SDK repos and is never edited in place. Repo-specific logic lives in `scripts/version` (reads/writes `src/manza/_version.py`) and `scripts/release-check` (install, fetch cassettes, ruff, mypy, pytest). `release.yml` gates on tag == package version. Publishing uses PyPI **OIDC trusted publishing** (no long-lived token) through the GitHub environment `pypi`; the PyPI trusted-publisher binding must name `getmanza/manza-python`, workflow `release.yml`, environment `pypi`. Verify at https://pypi.org/manage/project/manza/settings/publishing/ if it ever drifts.
- **Env vars: `MANZA_*` first, `ZAZU_*` fallback.** `src/manza/_env.py` reads `MANZA_<NAME>`, then the legacy `ZAZU_<NAME>` with a one-time `FutureWarning`, for all of 1.x. Fixture vars (`MANZA_FIXTURE_*`) have no fallback.
- **The repo moved from `getzazu/zazu-python` to `getmanza/manza-python`.** Remotes and URLs must say `getmanza/manza-python`.
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
python scripts/fetch_cassettes.py      # downloads manza-ruby's cassette tarball (no Manza API call)

# Daily loop
pytest tests/resources/test_customers.py    # while iterating
pytest                                      # full suite
ruff check                                  # lint
mypy                                        # types (strict, src/manza)

# Release (after PR merge, from a clean, up-to-date main)
bin/release list        # last releases + what patch/minor/major would give
bin/release --dry-run   # version + changes since the last tag, publishes nothing
bin/release minor       # or patch (default), major, an explicit 0.4.0; --force re-creates
# -> bumps src/manza/_version.py, runs scripts/release-check, pushes main, publishes the GH release
# -> release.yml publishes to PyPI via OIDC
```

## Workflow

- **Verify:** `ruff check` · `mypy` · `pytest` (all three, as in CI; `filterwarnings = error`)
- **Specs:** fast loop `pytest tests/resources/test_<resource>.py`; full suite `pytest` (replay: no network, needs `python scripts/fetch_cassettes.py` once); two worktrees at once: yes (cassettes are a git-ignored download, fetch in each)
- **CI:** required none; jobs `test (py3.11)` `test (py3.12)` `test (py3.13)` (`ci.yml`: install, fetch cassettes, ruff, mypy, pytest), check `cubic · AI code reviewer`; full suite on the PR; failure report none
- **Review bot:** cubic; push back, citing this file, on mocks instead of cassettes, camelCased wire keys, `# noqa` / `# type: ignore` / `cast` to quiet a tool, speculative abstractions
- **Merge:** squash — `gh pr merge <PR> --squash --delete-branch`; fallback after the gate: `--admin` for the required approving review
- **PR contract:** `## Summary` (`Closes #N`), `## Fable validation` (verdict, Not verified), `## Test plan`; backticks unescaped; labels none; screenshots none
- **Conflicts:** `CHANGELOG.md` — both sides under `## [Unreleased]`, main's first; `src/manza/_version.py` — main's; `tests/fixtures/cassettes/**` is git-ignored (refetch); `bin/release`, `release.yml` — main's (release kit)
- **Worktree setup:** `python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/python scripts/fetch_cassettes.py`; undo none
- **Release:** `bin/release [patch|minor|major|X.Y.Z]` from a clean, current main (`--dry-run` first; runs `scripts/release-check`) → `release.yml` publishes to PyPI; changelog `CHANGELOG.md`, `[Unreleased]` headed `## [X.Y.Z]` by hand; lockfiles none
- **Main health:** `gh run list --workflow ci.yml --branch main --event push --limit 1 --json conclusion,headSha`
- **Upstream:** libraries we own `getmanza/*`, `zoolutions/*` (release kit); scrub none

## Agent commands

The delivery skills come from the `flow` plugin (`.claude/settings.json`); this repository has no local commands. Sessions run on `opus` with `fable` as the advisor, consulted before a public API, anything irreversible, and when a failure repeats; `flow:fable-validator` checks a finished change before its PR opens.

## Cross-SDK contract

`manza-ruby` is the reference implementation:

- Records cassettes against `https://ma.manza.dev`
- Ships them as a release tarball (`cassettes-vX.Y.Z.tar.gz`) on each version
- All other SDKs (`manza-ts`, this repo, and the planned `manza-go`, `manza-rust`, ...) replay these cassettes in their own test harness

If the contract breaks (e.g. a new request shape), it's a coordinated change across at least manza-ruby and every SDK that consumes the tarball.

## Repository links

- Ruby SDK (reference): https://github.com/getmanza/manza-ruby
- TypeScript SDK: https://github.com/getmanza/manza-ts
- This repo: https://github.com/getmanza/manza-python
- PyPI package: https://pypi.org/project/manza/
- CLI consumer: https://github.com/getmanza/cli
