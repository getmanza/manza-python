"""The authorizer process (key B). Answers ``payment.authorization_requested``
webhooks::

    python authorizer.py        # listens on PORT from .env (default 4599)

1. Verify the delivery (401 when the signature or timestamp is bad).
2. Find the draft in your own ledger by its client_reference.
3. Missing or different from what you created: decline with a reason.
4. A payee not trusted yet (``payee_trusted: false``, only with "Approve
   transfers to new payees" on) is trusted by the authorize, unless
   ``allow_new_payees=False`` (ALLOW_NEW_PAYEES=false) declines it.
5. Otherwise sign the challenge from the ledger and authorize it.

It answers 200 first and does steps 2-5 on the executor (a background thread
by default): the delivery has a timeout, and a retried webhook is safe because
authorize replays idempotently. The server is the standard library's
``http.server``; the README shows the same handler under Flask and FastAPI.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import env_file
from ledger import Ledger

from manza import (
    Manza,
    ManzaArgumentError,
    ManzaConflictError,
    ManzaConnectionError,
    ManzaError,
    ManzaRateLimitError,
    ManzaResponse,
    ManzaServerError,
    transfer_authorization,
    webhook,
)

EVENT = "payment.authorization_requested"

# Ledger field -> webhook `data.payment` field. All must match.
CHECKED_FIELDS = {
    "payment_id": "id",
    "amount": "amount",
    "currency_code": "currency_code",
    "account_id": "account_id",
    "payee": "payee",
}

# Failures worth another try: the API did not answer, asked us to slow down,
# or was busy with a bank-detail edit, trust or revocation on the same payee
# (409 `authorization_busy`). Authorize and decline replay idempotently, so a
# retry is safe.
TRANSIENT_ERRORS = (ManzaServerError, ManzaConnectionError, ManzaRateLimitError)
BUSY = "authorization_busy"
ATTEMPTS = 3
MAX_RETRY_AFTER = 30  # seconds; a challenge expires, so never park the thread for long
MAX_BODY_BYTES = 1_000_000

Executor = Callable[[Callable[[], None]], Any]


def _in_a_thread(job: Callable[[], None]) -> None:
    threading.Thread(target=job).start()


class App:
    """``handle(body, headers)`` answers one delivery and returns the HTTP status.

    ``ledger_wait``: seconds to wait for the ledger entry. The webhook can arrive
    before create_transfer.py has written the entry from the create response.
    ``retry_delay``: base seconds between attempts. ``allow_new_payees=False``
    declines transfers to payees not trusted yet.
    """

    def __init__(
        self,
        *,
        client: Manza,
        secret: str,
        ledger: Ledger,
        executor: Executor = _in_a_thread,
        logger: logging.Logger | None = None,
        ledger_wait: float = 10,
        retry_delay: float = 2,
        allow_new_payees: bool = True,
    ) -> None:
        self._client = client
        self._secret = secret
        self._ledger = ledger
        self._executor = executor
        self._logger = logger or logging.getLogger("transfer_authorizer")
        self._ledger_wait = ledger_wait
        self._retry_delay = retry_delay
        self._allow_new_payees = allow_new_payees

    def handle(self, body: bytes, headers: webhook.Headers) -> int:
        event = self._verify(body, headers)
        if event is None:
            return 401
        if event.get("event") != EVENT:
            self._logger.info("ignoring %s: this app only answers %s", event.get("event"), EVENT)
            return 200

        data = event.get("data")
        self._executor(lambda: self._answer(data))
        return 200

    def _verify(self, body: bytes, headers: webhook.Headers) -> dict[str, Any] | None:
        try:
            event = webhook.construct_event(payload=body, headers=headers, secret=self._secret)
        except ManzaArgumentError as err:
            self._logger.warning("rejected a delivery: %s", err.message)
            return None
        self._logger.info(
            "received %s (%s), signature verified", event.get("event"), event.get("event_id")
        )
        return event

    def _answer(self, data: Any) -> None:
        try:
            payment = data["payment"]
            authorization = data["authorization"]
            client_reference = payment.get("client_reference")
            entry = self._wait_for_entry(client_reference)

            if entry is None:
                reason = f"client_reference {client_reference!r} is not in the ledger"
                self._decline(payment["id"], authorization["id"], reason)
                return
            mismatch = self._mismatch_reason(entry, payment)
            if mismatch:
                self._decline(payment["id"], authorization["id"], mismatch)
                return

            # Anything but True counts as new, so a webhook without the field is
            # declined under ALLOW_NEW_PAYEES=false rather than trusted blindly.
            if payment.get("payee_trusted") is not True:
                if not self._allow_new_payees:
                    self._decline(
                        payment["id"],
                        authorization["id"],
                        f"new payee {payment.get('payee')}: ALLOW_NEW_PAYEES=false declines "
                        "payees not trusted yet",
                    )
                    return
                self._logger.info(
                    "new payee %s, will be trusted on authorize", payment.get("payee")
                )

            self._logger.info(
                "ledger match for %s: %s %s to %s",
                client_reference,
                payment.get("amount"),
                payment.get("currency_code"),
                payment.get("payee"),
            )
            self._authorize(entry, authorization, client_reference, data.get("signature_input"))
        except ManzaError as err:
            self._logger.error(
                "API error %s: %s (type %r, request_id %r)",
                type(err).__name__,
                err.message,
                err.type,
                err.request_id,
            )
        except Exception as err:
            self._logger.error("could not answer the challenge: %s: %s", type(err).__name__, err)

    def _wait_for_entry(self, client_reference: Any) -> dict[str, Any] | None:
        deadline = time.monotonic() + self._ledger_wait
        while True:
            entry = self._ledger.find(client_reference) if client_reference else None
            if entry is not None or time.monotonic() >= deadline:
                return entry
            time.sleep(0.5)

    @staticmethod
    def _mismatch_reason(entry: dict[str, Any], payment: dict[str, Any]) -> str | None:
        for ledger_field, webhook_field in CHECKED_FIELDS.items():
            if entry.get(ledger_field) != payment.get(webhook_field):
                return (
                    f"{ledger_field} differs from the ledger (ledger {entry.get(ledger_field)!r}, "
                    f"webhook {payment.get(webhook_field)!r})"
                )
        return None

    # Sign from the ledger, never from the webhook: `signature_input` in the
    # webhook is only there to compare against.
    def _authorize(
        self,
        entry: dict[str, Any],
        authorization: dict[str, Any],
        client_reference: str | None,
        webhook_input: Any,
    ) -> None:
        signature_input = transfer_authorization.signature_input(
            payment_id=entry["payment_id"],
            nonce=authorization["nonce"],
            amount=entry["amount"],
            currency_code=entry["currency_code"],
            account_id=entry["account_id"],
            payee=entry["payee"],
            client_reference=client_reference,
        )
        # A signature over a different input is sure to fail, and failed
        # attempts count toward suspending the authorizer. Leave the challenge
        # unanswered instead: it expires and goes to your approvers.
        if signature_input != webhook_input:
            self._logger.warning(
                "signature input differs from the webhook's: ledger %r, webhook %r; not "
                "answering, the challenge goes to your approvers when it expires",
                signature_input,
                webhook_input,
            )
            return

        signature = transfer_authorization.sign(self._secret, signature_input)
        self._logger.info("signed the challenge for payment %s", entry["payment_id"])

        response = self._with_retries(
            lambda: self._client.payments.authorize(
                entry["payment_id"], authorization["id"], signature
            )
        )
        status = response.body.get("status") if isinstance(response.body, dict) else None
        self._logger.info("authorized payment %s (status %r)", entry["payment_id"], status)

    def _decline(self, payment_id: str, authorization_id: str, reason: str) -> None:
        self._with_retries(
            lambda: self._client.payments.decline(payment_id, authorization_id, reason)
        )
        self._logger.warning("declined payment %s: %s", payment_id, reason)

    def _with_retries(self, call: Callable[[], ManzaResponse]) -> ManzaResponse:
        attempt = 1
        while True:
            try:
                return call()
            except (*TRANSIENT_ERRORS, ManzaConflictError) as err:
                busy = not isinstance(err, ManzaConflictError) or err.type == BUSY
                if attempt >= ATTEMPTS or not busy:
                    raise
                if isinstance(err, ManzaRateLimitError) and err.retry_after:
                    delay: float = min(err.retry_after, MAX_RETRY_AFTER)
                else:
                    delay = self._retry_delay * attempt
                self._logger.warning(
                    "%s (request_id %r), retrying in %ss", type(err).__name__, err.request_id, delay
                )
                time.sleep(delay)
                attempt += 1


def make_handler(app: App, *, read_timeout: float = 10) -> type[BaseHTTPRequestHandler]:
    """An ``http.server`` request handler that feeds every POST to ``app``.
    A client silent for ``read_timeout`` seconds is dropped, so a stalled
    request never parks a thread."""

    class Handler(BaseHTTPRequestHandler):
        timeout = read_timeout

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            # read(-1) would wait for the client to hang up; a webhook is a few KB.
            if not 0 <= length <= MAX_BODY_BYTES:
                self._respond(400, b"bad request")
                return
            status = app.handle(self.rfile.read(length), self.headers)
            self._respond(status, b"ok" if status == 200 else b"unauthorized")

        def _respond(self, status: int, text: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(text)))
            self.end_headers()
            self.wfile.write(text)

    return Handler


def main() -> None:
    env_file.load()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    missing = [
        name
        for name in ("MANZA_AUTHORIZER_API_KEY", "MANZA_AUTHORIZER_SECRET")
        if not os.environ.get(name)
    ]
    if missing:
        sys.exit(f"Set {' and '.join(missing)} in {env_file.HERE / '.env'}")

    app = App(
        client=Manza(api_key=os.environ["MANZA_AUTHORIZER_API_KEY"]),
        secret=os.environ["MANZA_AUTHORIZER_SECRET"],
        ledger=Ledger(env_file.HERE / "ledger.json"),
        allow_new_payees=os.environ.get("ALLOW_NEW_PAYEES", "true").strip().lower()
        not in {"false", "0", "no"},
    )
    port = int(os.environ.get("PORT") or 4599)
    server = ThreadingHTTPServer(("", port), make_handler(app))
    logging.getLogger("transfer_authorizer").info("listening on port %d", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
