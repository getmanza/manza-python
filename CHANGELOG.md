# Changelog

All notable changes to `manza` (formerly `zazu-sdk`) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-11-14

Mirrors manza-ruby 2.0.0 and replays its `cassettes-v2.0.0`: synced to the
Manza API at getmanza/app `906ec486e5` (API version `2026-11-13`). A major
release: see Migrating from 1.x below.

### Removed

- **Breaking:** `client.invoices.create_payment_link` (`POST
  /api/invoices/:id/payment_link`). The API retired the endpoint: ask for the
  link with `generate_payment_link=True` on `invoices.create` or
  `invoices.update` instead.
- **Breaking:** the v1 transfer-authorization signer.
  `manza.transfer_authorization` builds only the v2 input (below).

### Changed

- **Breaking:** `transfer_authorization.SIGNATURE_VERSION` is
  `manza.transfer-authorization.v2`, and `signature_input` takes a required
  `transfer_method` keyword (`str | None`), appended after `client_reference`
  (`""` when None):
  `manza.transfer-authorization.v2|payment_id|nonce|amount|currency_code|account_id|payee|client_reference|transfer_method`.
  The API verifies v2 for every request that is unpinned or sends
  `Manza-Version: 2026-11-13`; only `2026-03-27` still verifies v1. Pass the
  payment's `transfer_method` as the API returned it. A call without it raises
  `TypeError` locally, never a failed signature attempt at the API.
- The example authorizer (`examples/transfer_authorizer`) records the create
  response's `transfer_method` in its ledger, checks it against the webhook's
  `payment.transfer_method`, signs v2, and compares its input with the
  webhook's `signature_input_v2`. `Ledger.record` takes `transfer_method`.
- Invoice docs: `account_id` is required on `invoices.create` (without one the
  API answers 422 `state_error`; an account that is not the entity's, 422 with
  `param` `account_id`), and `invoices.update` takes it too. An invoice's
  `status` may be `declined`, and `invoices.delete` also takes a `declined`
  invoice that has no number.
- The legacy `ZAZU_*` environment fallback and the `client.transfer_drafts`
  alias stay in 2.0 (as in manza-ruby 2.0.0); the `FutureWarning` now says the
  fallback goes in a later major release instead of "in 2.0".

### Added

- `ManzaPlanLimitReachedError`, a `ManzaValidationError` raised for a 422 whose
  `type` is `plan_limit_reached` (a plan cap, which the API used to answer with
  a 500). `kind`, `current` and `max` read the cap from the error body.
- `generate_payment_link` on `invoices.create` and `invoices.update` (needs the
  `payment_links:write` scope; taken only while payment links are enabled for
  the entity). Invoice responses carry `generate_payment_link` and the
  embedded `account`.
- `transfer_method` on `payments.create`: `eft` or `rtc` in South Africa,
  `standard` or `instant` in Morocco; one the market does not offer raises
  `ManzaValidationError` with `param` `transfer_method`. Payment responses
  carry `transfer_method` (the rail sent, the provider's default when left out,
  None where the market offers no choice).
- Documented: the authorization `refusal_reason` `rail_limit_exceeded` (status
  `superseded`): an authorized transfer over its rail's limit at execution,
  sent to the approvers; the authorize call raises a 422
  `ManzaValidationError` (`state_error`). A non-boolean
  `generate_payment_link` raises `ManzaValidationError` (400).
- Documented: the `payment.authorization_requested` webhook's
  `signature_input_v2` and `payment.transfer_method`, and
  `transfer_authorizer.get()`'s `trust_new_payees` and `new_payee_limit`.

### Fixed (API side, no wire change)

- `accounts.list_transactions` and `accounts.get_transaction` return posted
  movements only (getmanza/app 818432457a); the SDK is unchanged.

### Changed (tests)

- The cassette pin is `v2.0.0`. The invoice create/update cassettes, and the
  new `invoices/create_without_account`,
  `invoices/create_invalid_generate_payment_link` and
  `payments/create_invalid_transfer_method`, are replayed with exact body
  matching.

### Migrating from 1.x

- **`create_payment_link` is gone.** Replace
  `client.invoices.create_payment_link(id, account_id=acc)` with
  `client.invoices.update(id, account_id=acc, generate_payment_link=True)`, or
  pass `generate_payment_link=True` on create. `update` returns the invoice,
  not a link: the link is made from the invoice's account when the invoice is
  approved, and appears in the invoice's `payment_link`. `update` takes only an
  invoice that is still `draft`, `pending_approval` or `declined` (any other
  raises `ManzaValidationError`, `state_error`); for an invoice already
  approved or sent, there is no API path to attach a link to it:
  `client.payment_links.create(account_id=..., amount=..., ...)` makes a
  standalone link instead.
- **`account_id` is required on invoice create.** Pass the account the invoice
  is paid into (`client.accounts.list()`); 1.x calls without it now raise
  `ManzaValidationError`.
- **v2 signatures only.** Add `transfer_method=payment["transfer_method"]` to
  every `transfer_authorization.signature_input` call, and compare with the
  webhook's `signature_input_v2` instead of `signature_input`. A client pinned
  to `Manza-Version: 2026-03-27` (`api_version=` or `MANZA_API_VERSION`) is
  verified v1 and must stay on manza 1.x; unpin it, or pin `2026-11-13`, to
  move to 2.0.
- **Plan caps.** An `except ManzaServerError` around creates that may hit a
  plan cap no longer catches it: catch `ManzaPlanLimitReachedError` (or its
  parent `ManzaValidationError`), and do not retry it.

## [1.1.0]

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
