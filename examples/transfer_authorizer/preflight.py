"""Checks every setup step before you create a transfer, and says how to fix
the ones that fail::

    python preflight.py          # for a 10.00 transfer
    python preflight.py 250.00

✓ passed, ✗ failed (exit status 1), ! cannot be checked through the API.
"""

from __future__ import annotations

import math
import os
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import IO, Any
from urllib.parse import urlsplit

import env_file
import httpx

from manza import (
    Manza,
    ManzaAuthenticationError,
    ManzaError,
    ManzaForbiddenError,
    ManzaNotFoundError,
)
from manza.client import DEFAULT_BASE_URL

SECRET_MIN_DAYS = 7
# Hosts that hand out a new URL on every restart. An enrolled endpoint's URL is
# locked, so the next restart breaks the authorizer.
UNSTABLE_TUNNEL_HOSTS = ("ngrok-free.app", "trycloudflare.com")
SUSPENSION_FIXES = {
    "member": (
        "an approver suspended it: resume it in Settings → Developer → Transfer approval"
    ),
    "signature_failures": (
        "five invalid signatures in a row: fix the signing, then an approver resumes it in the app"
    ),
    "secret_expired": (
        "an approver rotates the secret in the app (and resumes it if it stays suspended); "
        "set the new one as MANZA_AUTHORIZER_SECRET"
    ),
    "endpoint_disabled": (
        "re-enable the webhook endpoint (webhook_endpoints.enable), or enrol a new one if it was "
        "deleted; if it stays suspended, an approver resumes it in the app"
    ),
}
# Plain decimals only: create_transfer.py sends the string as is, so "1/2" or
# "1e2" would parse here but not mean the same to the API.
PLAIN_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")


class Preflight:
    def __init__(
        self,
        *,
        env: Mapping[str, str] = os.environ,
        amount: str = "10.00",
        out: IO[str] = sys.stdout,
        now: datetime | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._env = env
        self._raw_amount = amount
        parsed = Decimal(amount) if PLAIN_DECIMAL.fullmatch(str(amount)) else None
        self._amount = parsed if parsed is not None and parsed > 0 else None
        self._out = out
        self._now = now or datetime.now(UTC)
        self._http_client = http_client
        self._creator: Manza | None = None
        self._authorizer_client: Manza | None = None
        self._ok = True

    def run(self) -> bool:
        """Prints one line per step; True when no step failed."""
        if self._amount is None:
            self._fail(
                f"amount {self._raw_amount!r} is not a positive decimal",
                "pass an amount like 10.00 or 250.00",
            )
        if not self._keys():
            return self._ok

        self._creator_reaches_entity()
        authorizer = self._enrolled_authorizer()
        if authorizer is not None:
            self._currency_matches(authorizer)
            # An expired secret already failed the authorizer line, with its fix.
            if authorizer.get("suspension_reason") != "secret_expired":
                self._secret_fresh(authorizer)
        self._secret_set()
        if authorizer is not None:
            self._endpoint_enabled(authorizer)
            if self._amount is not None:
                self._amount_within_limits(authorizer, self._amount)
        self._payee_trusted()
        return self._ok

    # 1. Both keys (and the ids the other steps read) are set, the keys different.
    def _keys(self) -> bool:
        names = (
            "MANZA_CREATOR_API_KEY",
            "MANZA_AUTHORIZER_API_KEY",
            "MANZA_ACCOUNT_ID",
            "MANZA_BENEFICIARY_ID",
        )
        missing = [name for name in names if not self._value(name)]
        if missing:
            self._fail(f"{', '.join(missing)} not set", "set them in .env")
            return False
        if self._value("MANZA_CREATOR_API_KEY") == self._value("MANZA_AUTHORIZER_API_KEY"):
            self._fail(
                "key A and key B are the same key",
                "use two different keys: the API refuses to let the key that created a "
                "transfer authorize it",
            )
            return False
        self._pass("key A and key B are set and different")
        self._warn(
            "the API does not show key A's transfers:write scope, key B's transfers:authorize "
            "scope or key B's IP allowlist",
            "check them in Settings → Developer → API keys: key B needs both to authorize",
        )
        return True

    # 2. Key A reaches the API.
    def _creator_reaches_entity(self) -> None:
        try:
            entity = self._creator_client().entity.get().body
        except ManzaError as err:
            self._fail(
                f"key A cannot read the entity: {_describe(err)}",
                _key_fix(err, "MANZA_CREATOR_API_KEY", "entity:read"),
            )
            return
        self._pass(f"key A reaches the API (entity {entity.get('name')!r})")

    # 3. Key B reads the authorizer, which must be active.
    def _enrolled_authorizer(self) -> dict[str, Any] | None:
        try:
            authorizer: dict[str, Any] = self._authorizer().transfer_authorizer.get().body
        except ManzaNotFoundError:
            self._fail(
                "no transfer authorizer is enrolled",
                "enrol your webhook endpoint in Settings → Developer → Transfer approval",
            )
            return None
        except ManzaError as err:
            self._fail(
                f"key B cannot read the transfer authorizer: {_describe(err)}",
                _key_fix(err, "MANZA_AUTHORIZER_API_KEY", "transfers:authorize"),
            )
            return None

        if authorizer.get("status") == "active":
            self._pass("transfer authorizer is active")
        else:
            reason = authorizer.get("suspension_reason")
            self._fail(
                f"transfer authorizer is {authorizer.get('status')} ({reason})",
                SUSPENSION_FIXES.get(
                    str(reason), "see suspension_reason in the transfer authorization docs"
                ),
            )
        return authorizer

    def _currency_matches(self, authorizer: dict[str, Any]) -> None:
        account_id = self._value("MANZA_ACCOUNT_ID")
        try:
            currency = self._creator_client().accounts.get(account_id).body.get("currency_code")
        except ManzaError as err:
            self._fail(
                f"key A cannot read account {account_id!r}: {_describe(err)}",
                _key_fix(err, "MANZA_CREATOR_API_KEY", "accounts:read", "MANZA_ACCOUNT_ID"),
            )
            return
        enrolled = authorizer.get("currency_code")
        if currency == enrolled:
            self._pass(f"account currency {currency} is the enrolled currency")
            return
        self._fail(
            f"account currency {currency} is not the enrolled currency {enrolled}",
            f"pay from a {enrolled} account (MANZA_ACCOUNT_ID), or enrol {currency}",
        )

    def _secret_fresh(self, authorizer: dict[str, Any]) -> None:
        expires_at = datetime.fromisoformat(authorizer["secret_expires_at"])
        days = math.floor((expires_at - self._now).total_seconds() / 86_400)
        if days >= SECRET_MIN_DAYS:
            self._pass(f"signing secret expires in {days} days")
            return
        when = "expired" if days < 0 else f"expires in {days} days"
        self._fail(
            f"signing secret {when} ({authorizer['secret_expires_at']})",
            "an approver should rotate the secret in Settings → Developer → Transfer approval; "
            "set the new one as MANZA_AUTHORIZER_SECRET",
        )

    # 4. The signing secret is set.
    def _secret_set(self) -> None:
        if self._value("MANZA_AUTHORIZER_SECRET"):
            self._pass("MANZA_AUTHORIZER_SECRET is set")
            self._warn(
                "the API cannot confirm MANZA_AUTHORIZER_SECRET is the enrolled endpoint's current "
                "secret",
                "copy it again from enrolment or the last rotation: five invalid signatures in a "
                "row suspend the authorizer",
            )
            return
        self._fail(
            "MANZA_AUTHORIZER_SECRET is not set",
            "set it to the signing secret shown at enrolment or at the last rotation",
        )

    # 5. The enrolled webhook endpoint is enabled, on a URL that lasts.
    def _endpoint_enabled(self, authorizer: dict[str, Any]) -> None:
        endpoint_id = authorizer.get("webhook_endpoint_id")
        try:
            endpoint = self._creator_client().webhook_endpoints.get(str(endpoint_id)).body
        except ManzaNotFoundError:
            self._fail(
                f"the enrolled webhook endpoint {endpoint_id} was deleted",
                "create an endpoint at a stable URL and enrol it in Settings → Developer → "
                "Transfer approval",
            )
            return
        except ManzaError as err:
            self._fail(
                f"key A cannot read the enrolled webhook endpoint: {_describe(err)}",
                _key_fix(err, "MANZA_CREATOR_API_KEY", "webhook_endpoints:read"),
            )
            return

        url = endpoint.get("url")
        if endpoint.get("status") == "active":
            self._pass(f"webhook endpoint {url} is enabled")
        else:
            self._fail(
                f"webhook endpoint {url} is {endpoint.get('status')}",
                f"enable it (webhook_endpoints.enable({endpoint.get('id')!r})); if the "
                "authorizer stays suspended, an approver resumes it in the app",
            )
        host = urlsplit(str(url or "")).hostname or ""
        unstable = next((d for d in UNSTABLE_TUNNEL_HOSTS if host.endswith(d)), None)
        if unstable:
            self._warn(
                f"webhook endpoint is on {unstable}, whose URL changes when the tunnel restarts",
                "use a reserved domain or a named tunnel, then enrol an endpoint at that URL",
            )

    # 6a. The test amount fits both limits.
    def _amount_within_limits(self, authorizer: dict[str, Any], amount: Decimal) -> None:
        per_transfer = Decimal(str(authorizer["per_transfer_limit"]))
        room = Decimal(str(authorizer["daily_limit"])) - Decimal(
            str(authorizer["daily_authorized_total"])
        )
        if amount > per_transfer:
            self._fail(
                f"{amount:.2f} is over the limit per transfer ({per_transfer:.2f})",
                f"send at most {per_transfer:.2f}, or have an approver raise the limit",
            )
        elif amount > room:
            self._fail(
                f"{amount:.2f} does not fit the last 24 hours' room ({room:.2f} left)",
                "wait for older authorizations to leave the 24-hour window, or have an approver "
                "raise the limit",
            )
        else:
            self._pass(f"{amount:.2f} is within the limit per transfer and the 24-hour room")

    # 6b. The payee is trusted, or may be trusted on authorize.
    def _payee_trusted(self) -> None:
        beneficiary_id = self._value("MANZA_BENEFICIARY_ID")
        try:
            beneficiary = self._creator_client().beneficiaries.get(beneficiary_id).body
        except ManzaError as err:
            self._fail(
                f"key A cannot read beneficiary {beneficiary_id!r}: {_describe(err)}",
                _key_fix(
                    err, "MANZA_CREATOR_API_KEY", "beneficiaries:read", "MANZA_BENEFICIARY_ID"
                ),
            )
            return
        accounts = beneficiary.get("external_accounts") or []
        account = next((a for a in accounts if a.get("default")), None)
        if account is None:
            self._fail(
                "beneficiary has no default bank account",
                "add one, or set a beneficiary that has one",
            )
            return
        if account.get("trusted"):
            self._pass(f"payee {account.get('id')} is trusted")
            return
        self._warn(
            f"payee {account.get('id')} is not trusted yet",
            "it qualifies only with \"Approve transfers to new payees\" on in Settings → "
            "Developer → Transfer approval (not visible through the API), key A bound to an IP "
            "allowlist, and the amount within the limit per transfer to a new payee, and only if "
            "its bank details were never trusted (revoked or edited details always go to your "
            "approvers); otherwise have an approver trust it",
        )

    def _creator_client(self) -> Manza:
        if self._creator is None:
            self._creator = self._client("MANZA_CREATOR_API_KEY")
        return self._creator

    def _authorizer(self) -> Manza:
        if self._authorizer_client is None:
            self._authorizer_client = self._client("MANZA_AUTHORIZER_API_KEY")
        return self._authorizer_client

    def _client(self, key_var: str) -> Manza:
        return Manza(
            api_key=self._value(key_var),
            base_url=self._value("MANZA_BASE_URL") or DEFAULT_BASE_URL,
            http_client=self._http_client,
        )

    def _value(self, name: str) -> str:
        return str(self._env.get(name) or "")

    def _pass(self, message: str) -> None:
        print(f"✓ {message}", file=self._out)

    def _fail(self, message: str, fix: str) -> None:
        self._ok = False
        print(f"✗ {message}: {fix}", file=self._out)

    def _warn(self, message: str, note: str) -> None:
        print(f"! {message}: {note}", file=self._out)


def _describe(error: ManzaError) -> str:
    return f"{type(error).__name__} {error.type or error.status}: {error.message}"


def _key_fix(error: ManzaError, key_var: str, scope: str, id_var: str | None = None) -> str:
    if isinstance(error, ManzaAuthenticationError):
        return f"check {key_var}: the key is wrong or revoked"
    if isinstance(error, ManzaForbiddenError):
        return f"give the key the {scope} scope, or add this machine's address to its IP allowlist"
    if isinstance(error, ManzaNotFoundError):
        return f"check {id_var or 'MANZA_BASE_URL'}"
    return "check MANZA_BASE_URL and the network, then rerun"


def main() -> None:
    env_file.load()
    amount = sys.argv[1] if len(sys.argv) > 1 else "10.00"
    sys.exit(0 if Preflight(amount=amount).run() else 1)


if __name__ == "__main__":
    main()
