# Changelog

All notable changes to `zazu-sdk` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `ZazuConflictError` (409), the 10th error class. A duplicate
  `client_reference` on a transfer draft raises it with `payment_id`
  naming the existing draft. 400 now maps to `ZazuValidationError`
  (lists return 400 for a malformed `limit`/`cursor`).
- `TransferDrafts.authorize(id, authorization_id, signature)` and
  `decline(id, authorization_id, reason=None)` for machine-authorized
  transfers. A blank signature raises `ZazuArgumentError` locally, because
  the API would count it as a failed attempt.
- `TransferDrafts.create` documents the new optional `client_reference`;
  responses carry `client_reference` and `authorization`.
- `zazu_sdk.transfer_authorization` with `signature_input`, `sign` and
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

- Default base URL is now `https://ma.manza.finance` (Morocco production;
  South Africa is `https://za.manza.finance`). Cassettes are recorded against
  `https://ma.manza.dev`.
- Request bodies are serialized compactly (no spaces after `,` and `:`), the
  same bytes the Ruby SDK sends.
- Replay harness: one cassette per test, with optional exact and
  signature-less body matching for the new cassettes.

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
