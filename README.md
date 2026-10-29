# manza

Python SDK for the [Manza API](https://ma.manza.finance).

## Install

```bash
pip install manza
```

Requires Python 3.11+.

## Quick start

```python
from manza import Manza

client = Manza(api_key="sk_live_...")

client.entity.get()
client.accounts.list(currency_code="MAD")
client.customers.list(q="Acme")
client.customers.create(
    customer_type="business",
    company_name="Acme Corp",
    email="billing@acme.com",
)

client.invoices.list()
client.payment_links.cancel(payment_link_id)
client.webhook_endpoints.list()

client.checkout_sessions.create(
    account_id=account_id,
    amount="100.00",
    success_url="https://example.com/ok",
    cancel_url="https://example.com/cancel",
)
client.checkout_sessions.get(session_id)
```

The client picks up `MANZA_API_KEY`, `MANZA_BASE_URL`, `MANZA_API_VERSION`, and
`MANZA_TIMEOUT` from the environment if you don't pass them. The old `ZAZU_*`
names still work for all of 1.x and emit a one-time `FutureWarning`.

### Hosts

The default base URL is `https://ma.manza.finance` (Morocco). For South Africa:

```python
client = Manza(api_key="sk_live_...", base_url="https://za.manza.finance")
```

The replay tests run against the staging host `https://ma.manza.dev`.

## Beneficiaries and trusted payees

```python
beneficiary = client.beneficiaries.create(
    beneficiary_type="business",  # "individual" | "business"
    company_name="Acme Corp",
    email="ap@acme.com",
).body

account = client.beneficiaries.create_external_account(
    beneficiary["id"], account_number="..."  # bank_identifier is required in ZA only
).body
client.beneficiaries.list_external_accounts(beneficiary["id"])  # Page
client.beneficiaries.get_external_account(beneficiary["id"], account["id"])

# Ask for the account to be trusted; a member approves it in the app.
request = client.payee_trust_requests.create([account["id"]]).body
client.payee_trust_requests.get(request["id"])
```

## Transfers and machine authorization

```python
draft = client.payments.create(
    account_id=account_id,
    beneficiary_id=beneficiary_id,
    amount="250.00",
    client_reference="po_1",  # unique per entity, at most 128 characters
).body
client.payments.get(draft["id"])  # authorization: status, refusal_reason

client.transfer_authorizer.get()  # status, suspension_reason, limits, daily_authorized_total
```

A duplicate `client_reference` raises `ManzaConflictError` with `payment_id`
naming the existing draft. `transfer_authorizer.get()` raises
`ManzaNotFoundError` when no authorizer is enrolled. `client.transfer_drafts` is
a deprecated alias of `client.payments` (same methods, `/api/payments`); it
emits a `DeprecationWarning`.

A draft inside your entity's authorization envelope (trusted payee, or a new one
when you allow it, within limits) is sent to your enrolled authorizer endpoint
as a `payment.authorization_requested` webhook carrying an `authorization.id`
and a one-time `nonce`. Your system checks it against its own ledger, signs it
and authorizes it with a **different API key** from the one that created it.
[`examples/transfer_authorizer/`](examples/transfer_authorizer/) runs the whole
flow. The [transfer authorization docs](https://ma.manza.finance/docs/api/transfer-authorization)
cover every step below.

### Setup, step by step

1. **Feature flags.** Ask support to enable API transfers and transfer authorization (`release_api_webhook_authorization`) on your workspace.
2. **Two API keys.** Key A creates drafts (`transfers:write`; `beneficiaries:request_trust` for step 6; `entity:read`, `accounts:read`, `webhook_endpoints:read` and `beneficiaries:read` for the preflight in step 7). Key B answers the challenges (`transfers:authorize`). The creating key is always refused with 403 `same_key_forbidden`, so keep key B and the signing secret on the system that holds your ledger. Bind key B to an IP allowlist: authorizing from a key without one is refused with 403 `unrestricted_api_key`. Bind key A to one too if you allow new payees (step 6): a draft to a new payee from a key without an allowlist goes to your approvers (`unrestricted_api_key`).
3. **A stable public URL.** Your authorizer needs an HTTPS URL that never changes: an enrolled endpoint's URL is locked. Use a reserved ngrok domain (`ngrok http --url=your-name.ngrok.app 4599`) or a named Cloudflare tunnel. Never a free ngrok URL: it changes on every restart.
4. **Create the webhook endpoint** at that URL:

   ```python
   client.webhook_endpoints.create(url="https://your-name.ngrok.app/", events=["transfer.executed"])
   ```

   The challenge, `payment.authorization_requested`, needs no subscription: once the endpoint is enrolled (step 5), it is delivered there directly, and it cannot be listed in `events`.

5. **Enrol it in the app**: Settings → Developer → Transfer approval. Pick the endpoint, the currency and both limits, confirm with your two-factor code, and copy the signing secret: it is shown once.
6. **Allow new payees, or trust each payee.** Turn on *Approve transfers to new payees* at enrolment (or later, same page, with your two-factor code) and set the *Limit per transfer to a new payee*. Your authorizer may then approve a transfer to bank details your workspace never trusted, up to that limit, and its signature trusts them: the webhook's `payment.payee_trusted` is `false` for such a transfer. Bank details whose trust was revoked, or that were edited after trusting, still go to your approvers. Without the option, an approver marks the beneficiary's bank account as trusted from the Beneficiaries list, or you ask them to:

   ```python
   client.payee_trust_requests.create(["01a1..."])
   ```

   `trusted` on `client.beneficiaries.get_external_account(...)` says which it is. The API does not show whether the option is on.
7. **Run the preflight, then the example** (from `examples/transfer_authorizer/`, after installing `manza` and filling in `.env`): `python preflight.py` checks what the API shows of steps 1–6 and prints a fix for each that fails. What it cannot see, check by hand: that key B is bound to an IP allowlist, and, for a payee not trusted yet, that *Approve transfers to new payees* is on and key A is bound to an IP allowlist too (it warns, it does not fail). Then `python authorizer.py` in one terminal, `python create_transfer.py` in another.
8. **Troubleshooting**: a draft that goes to your approvers instead has an `authorization` with status `refused` and a `refusal_reason` (`create_transfer.py` prints it in words); `client.transfer_authorizer.get()` shows a suspension and its `suspension_reason`. An authorize answered 409 `authorization_busy` (a bank-detail edit, trust or trust revocation on the same payee was in flight) is safe to retry. The reasons, and an API error's `type`, are in the [transfer authorization docs](https://ma.manza.finance/docs/api/transfer-authorization).

### Verifying the webhook

Pass the **raw request body** (bytes or str), never re-serialized JSON.
`webhook.construct_event` reads `X-Manza-Signature` and `X-Manza-Timestamp`
(any case, the WSGI `HTTP_X_MANZA_*` form, or the legacy `X-Zazu-*` names) from
any headers object with `items()` (a dict, Flask's or Starlette's headers,
`http.server`'s `self.headers`) or ASGI's raw `scope["headers"]` byte pairs, checks the signature in constant time and the
timestamp within 5 minutes, and returns the parsed event (a dict). It raises
`ManzaArgumentError` otherwise:

```python
from manza import ManzaArgumentError, webhook

try:
    event = webhook.construct_event(
        payload=request.get_data(), headers=request.headers, secret=signing_secret
    )
except ManzaArgumentError as err:
    return str(err), 401
```

`webhook.verify(payload=..., signature=..., timestamp=..., secret=...)` returns
a bool instead. Both accept `tolerance=None` to skip the timestamp check. Use it
only to replay a captured delivery in a local tool or test, never on a live
endpoint: without the check, anyone holding a captured delivery can replay it.

### Signing the challenge

Sign the draft from **your own record** of it with the endpoint's signing
secret, using `manza.transfer_authorization`:

```python
import os

from manza import Manza, transfer_authorization as ta

signature_input = ta.signature_input(
    payment_id=draft["id"],
    nonce=event["data"]["authorization"]["nonce"],
    amount=draft["amount"],  # the API's decimal string, verbatim, e.g. "2500.0"
    currency_code=draft["currency_code"],
    account_id=draft["account_id"],
    payee=ta.payee_for(external_account_id=draft["external_account_id"]),
    client_reference=draft["client_reference"],
)
signature = ta.sign(signing_secret, signature_input)  # lowercase hex HMAC-SHA256

authorizer = Manza(api_key=os.environ["MANZA_AUTHORIZER_API_KEY"])
authorizer.payments.authorize(draft["id"], event["data"]["authorization"]["id"], signature)
# or: authorizer.payments.decline(draft["id"], event["data"]["authorization"]["id"], "reason")
```

`payee_for` takes exactly one of `external_account_id` / `destination_account_id`.
A blank signature raises `ManzaArgumentError` before any request is made. A
wrong signature raises `ManzaValidationError` (`type` `invalid_signature`). Five
on one challenge send the draft to your in-app approvers; five in a row suspend
the authorizer.

## Pagination

List endpoints return a `Page`. Iterate one page or chase cursors:

```python
page = client.invoices.list(limit=25)
for invoice in page:
    ...

# All items, automatic cursor chasing:
for invoice in client.invoices.list().auto_paging_iter():
    ...
```

## Errors

Ten concrete subclasses; discriminate with `isinstance`. `ManzaValidationError`
covers 400 and 422, `ManzaConflictError` covers 409 and exposes `payment_id`:

```python
from manza import (
    ManzaValidationError,
    ManzaRateLimitError,
    ManzaNotFoundError,
)

try:
    client.invoices.get("nope")
except ManzaNotFoundError as err:
    print(err.status, err.request_id, err.body)
except ManzaRateLimitError as err:
    print("retry after", err.retry_after, "seconds")
```

## Cross-SDK contract

`manza` is one of several Manza SDKs that all replay cassettes recorded by
the canonical [`manza-ruby`](https://github.com/getmanza/manza-ruby) SDK against
staging (`ma.manza.dev`). The wire format is snake_case JSON; request and response shapes match
across every Manza SDK.

## The SDK family

| SDK | Repository | Install |
|---|---|---|
| Ruby (reference implementation, records the cassettes) | [getmanza/manza-ruby](https://github.com/getmanza/manza-ruby) | `gem "manza"` |
| TypeScript / JavaScript | [getmanza/manza-ts](https://github.com/getmanza/manza-ts) | `npm install @getmanza/sdk` |
| Python | [getmanza/manza-python](https://github.com/getmanza/manza-python) (this repo) | `pip install manza` |
| Go | [getmanza/manza-go](https://github.com/getmanza/manza-go) | `go get github.com/getmanza/manza-go` |
| PHP | [getmanza/manza-php](https://github.com/getmanza/manza-php) | `composer require manza/manza-php` |
| Rust | [getmanza/manza-rust](https://github.com/getmanza/manza-rust) | `cargo add manza` |
| Crystal | [getmanza/manza-crystal](https://github.com/getmanza/manza-crystal) | shard `manza` (`github: getmanza/manza-crystal`) |
| Elixir | [getmanza/manza-elixir](https://github.com/getmanza/manza-elixir) | `{:manza, "~> 1.0"}` |
| CLI | [getmanza/cli](https://github.com/getmanza/cli) | `npm install -g @getzazu/cli` or `brew install getmanza/tap/zazu` |

## License

MIT.
