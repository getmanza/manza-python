# zazu-sdk

Python SDK for the [Manza API](https://ma.manza.finance).

## Install

```bash
pip install zazu-sdk
```

Requires Python 3.11+.

## Quick start

```python
from zazu_sdk import Zazu

client = Zazu(api_key="sk_live_...")

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

The client picks up `ZAZU_API_KEY`, `ZAZU_BASE_URL`, `ZAZU_API_VERSION`, and
`ZAZU_TIMEOUT` from the environment if you don't pass them.

### Hosts

The default base URL is `https://ma.manza.finance` (Morocco). For South Africa:

```python
client = Zazu(api_key="sk_live_...", base_url="https://za.manza.finance")
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
draft = client.transfer_drafts.create(
    account_id=account_id,
    beneficiary_id=beneficiary_id,
    amount="150.00",
    client_reference="po_1",  # unique per entity, at most 128 characters
).body
```

A duplicate `client_reference` raises `ZazuConflictError` with `payment_id`
naming the existing draft. A draft inside the entity's machine-authorization
envelope is sent to the enrolled authorizer as a
`payment.authorization_requested` webhook. Answer it with a different API key
holding `transfers:authorize`, signing with `zazu_sdk.transfer_authorization`:

```python
from zazu_sdk import transfer_authorization as ta

signature_input = ta.signature_input(
    payment_id=draft["id"],
    nonce=nonce,  # from the webhook
    amount=draft["amount"],  # the API's decimal string, verbatim
    currency_code=draft["currency_code"],
    account_id=draft["account_id"],
    payee=ta.payee_for(external_account_id=draft["external_account_id"]),
    client_reference=draft["client_reference"],
)
signature = ta.sign(signing_secret, signature_input)  # lowercase hex HMAC-SHA256

authorizer.transfer_drafts.authorize(draft["id"], authorization_id, signature)
# or: authorizer.transfer_drafts.decline(draft["id"], authorization_id, "reason")
```

`payee_for` takes exactly one of `external_account_id` / `destination_account_id`.
A blank signature raises `ZazuArgumentError` before any request is made.

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

Ten concrete subclasses; discriminate with `isinstance`. `ZazuValidationError`
covers 400 and 422, `ZazuConflictError` covers 409 and exposes `payment_id`:

```python
from zazu_sdk import (
    ZazuValidationError,
    ZazuRateLimitError,
    ZazuNotFoundError,
)

try:
    client.invoices.get("nope")
except ZazuNotFoundError as err:
    print(err.status, err.request_id, err.body)
except ZazuRateLimitError as err:
    print("retry after", err.retry_after, "seconds")
```

## Cross-SDK contract

`zazu-sdk` is one of several Zazu SDKs that all replay cassettes recorded by
the canonical [`zazu-ruby`](https://github.com/getzazu/zazu-ruby) SDK against
staging (`ma.manza.dev`). The wire format is snake_case JSON; request and response shapes match
across Ruby, TypeScript, Python, Go, and Rust.

## License

MIT.
