# Changelog

All notable changes to `manza` (formerly `zazu-sdk`) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Mirrors manza-ruby 1.2.0 and 1.3.0.

### Added

- `client.payments` (`Payments`): `create`, `get`, `authorize` and `decline`
  on the API's canonical paths, `POST /api/payments`, `GET /api/payments/:id`,
  `POST /api/payments/:id/authorize` and `POST /api/payments/:id/decline`. The
  API renamed transfer drafts to payments; request and response bodies are
  unchanged, and so is the `manza.transfer_authorization` signature input.
- `client.transfer_authorizer.get()` (`GET /api/transfer_authorizer`): the
  enrolled authorizer's `status`, `suspension_reason`, limits,
  `daily_authorized_total`, `secret_expires_at` and `webhook_endpoint_id`.
  Raises `ManzaNotFoundError` when none is enrolled.
- `manza.webhook` verifies incoming webhook deliveries: `verify` (bool),
  `construct_event` (returns the parsed event, raises `ManzaArgumentError`)
  and `sign`. Takes the raw body as bytes or str and reads `X-Manza-*` headers
  in any case, the WSGI `HTTP_X_MANZA_*` form and the legacy `X-Zazu-*` names
  from any headers object with `items()` or ASGI's raw byte pairs; checks
  the timestamp within 5
  minutes (`tolerance=None` skips it, for local replay only). Tested with the
  fixed vector shared across SDKs. No new error class.
- Documented the new pass-through fields: a draft's `authorization` carries
  `refusal_reason` (status `refused` when it went to the approvers at create
  time), bank accounts carry `trusted`, and the challenge webhook's
  `payment.payee_trusted` says whether the payee was trusted already.
- `examples/transfer_authorizer/`: a runnable two-key transfer authorizer on
  the standard library's `http.server` (`authorizer.py`), a creator script
  that prints where the API routed the draft, a JSON ledger and a
  `preflight.py` that checks every setup step and prints the fix. Not shipped
  in the package.
- README: "Setup, step by step" for machine-authorized transfers, a verifier
  snippet, and the example README's Flask and FastAPI snippets.

### Deprecated

- `client.transfer_drafts` and `TransferDrafts`. Both keep working for all of
  1.x: the accessor returns `client.payments` and the class name is the same
  class, so the old name now calls `/api/payments` too. The accessor emits a
  `DeprecationWarning` (shown when deprecation warnings are on). The server
  keeps `/api/transfer_drafts` as a permanent alias.

### Changed

- Cassettes are fetched from manza-ruby `v1.3.0` (`cassettes-v1.3.0.tar.gz`).
  The nine payment cassettes moved from `transfer_drafts/` to `payments/` and
  match the `/api/payments…` URIs; `payments/create` and `beneficiaries/create`
  match the new recorded request bodies. `tests/fixture_ids.py` gains the
  refused and new-payee fixtures (34 entries, identical to manza-ruby's).

## [1.0.0]

### Added

- `ManzaConflictError` (409), the 10th error class. A duplicate
  `client_reference` on a transfer draft raises it with `payment_id`
  naming the existing draft. 400 now maps to `ManzaValidationError`
  (lists return 400 for a malformed `limit`/`cursor`).
- `TransferDrafts.authorize(id, authorization_id, signature)` and
  `decline(id, authorization_id, reason=None)` for machine-authorized
  transfers. A blank signature raises `ManzaArgumentError` locally, because
  the API would count it as a failed attempt.
- `TransferDrafts.create` documents the new optional `client_reference`;
  responses carry `client_reference` and `authorization`.
- `manza.transfer_authorization` with `signature_input`, `sign` and
  `payee_for`, the HMAC-SHA256 signer for authorization challenges, tested
  with the fixed vector shared across SDKs.
- `Beneficiaries.create`, `list_external_accounts`, `get_external_account`
  and `create_external_account`.
- `PayeeTrustRequests` (`client.payee_trust_requests`) with
  `create(external_account_ids)` and `get(id)`.
- Docs for new pass-through fields: checkout session `customer_name`,
  `collect_billing_address`, `billing_address`, `settled_at`, `transaction`
  and the `clearing` status; payment link billing fields; customer
  `registration_number` / `vat_number` (and MA-only `tax_id` / `ice_number`).

### Changed

- **Renamed from `zazu-sdk` to `manza`** (1.0.0 under the new name; see the
  migration guide below). The package, import, classes, User-Agent and
  environment variables all move from Zazu to Manza.
- The version header is now `Manza-Version` (the API accepts both).
- User-Agent is `manza-python/<version>` (was `zazu-sdk/<version>`).
- Cassettes are fetched from `getmanza/manza-ruby`, pinned to `v1.0.0`.
- The replay placeholders are `<MANZA_API_KEY>` / `<MANZA_VERSION>` and the
  fixture variables are `MANZA_FIXTURE_*` (no fallback, dev-only).
- Default base URL is now `https://ma.manza.finance` (Morocco production;
  South Africa is `https://za.manza.finance`). Cassettes are recorded against
  `https://ma.manza.dev`.
- Request bodies are serialized compactly (no spaces after `,` and `:`), the
  same bytes the Ruby SDK sends.
- Replay harness: one cassette per test, with optional exact and
  signature-less body matching for the new cassettes.

### Deprecated

- `ZAZU_API_KEY`, `ZAZU_BASE_URL`, `ZAZU_API_VERSION` and `ZAZU_TIMEOUT` still
  work for all of 1.x. `MANZA_*` wins when both are set; the legacy name emits
  one `FutureWarning` per variable per process.

### Migrating from `zazu-sdk` 0.x

| Before | After |
|---|---|
| `pip install zazu-sdk` | `pip install manza` |
| `from zazu_sdk import Zazu` | `from manza import Manza` |
| `ZazuError`, `ZazuValidationError`, ... (every `Zazu*` class) | `ManzaError`, `ManzaValidationError`, ... |
| `zazu_sdk.transfer_authorization` | `manza.transfer_authorization` |
| `ZAZU_API_KEY` / `ZAZU_BASE_URL` / `ZAZU_API_VERSION` / `ZAZU_TIMEOUT` | `MANZA_API_KEY` / `MANZA_BASE_URL` / `MANZA_API_VERSION` / `MANZA_TIMEOUT` |
| `Zazu-Version` header | `Manza-Version` |
| repo `getzazu/zazu-python` | `getmanza/manza-python` |

## [0.2.1]

Version alignment: the whole SDK family now releases in lockstep with zazu-ruby. No functional changes since [0.1.0].

## [0.1.0]

Initial release.

### Added

- Sync `Zazu` client built on `httpx`
- Resource modules: `accounts`, `beneficiaries`, `checkout_sessions`, `customers`, `entity`, `invoices`, `payment_links`, `transfer_drafts`, `webhook_endpoints`
- Cursor-based `Page` with `auto_paging_iter()`
- Nine-class error hierarchy mirroring `zazu-ruby`
- Cassette-replay test harness driven by the Ruby SDK's release tarball
