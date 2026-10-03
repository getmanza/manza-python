"""Manza Python SDK. Mirrors lib/manza.rb."""

from . import transfer_authorization
from ._version import __version__
from .client import Manza
from .errors import (
    ManzaArgumentError,
    ManzaAuthenticationError,
    ManzaConfigurationError,
    ManzaConflictError,
    ManzaConnectionError,
    ManzaError,
    ManzaForbiddenError,
    ManzaNotFoundError,
    ManzaRateLimitError,
    ManzaServerError,
    ManzaValidationError,
)
from .page import MAX_PER_PAGE, Page
from .resources.accounts import Accounts
from .resources.beneficiaries import Beneficiaries
from .resources.checkout_sessions import CheckoutSessions
from .resources.customers import Customers
from .resources.entity import Entity
from .resources.invoices import Invoices
from .resources.payee_trust_requests import PayeeTrustRequests
from .resources.payment_links import PaymentLinks
from .resources.transfer_drafts import TransferDrafts
from .resources.webhook_endpoints import WebhookEndpoints
from .response import ManzaResponse

VERSION = __version__

__all__ = [
    "MAX_PER_PAGE",
    "VERSION",
    "Accounts",
    "Beneficiaries",
    "CheckoutSessions",
    "Customers",
    "Entity",
    "Invoices",
    "Manza",
    "ManzaArgumentError",
    "ManzaAuthenticationError",
    "ManzaConfigurationError",
    "ManzaConflictError",
    "ManzaConnectionError",
    "ManzaError",
    "ManzaForbiddenError",
    "ManzaNotFoundError",
    "ManzaRateLimitError",
    "ManzaResponse",
    "ManzaServerError",
    "ManzaValidationError",
    "Page",
    "PayeeTrustRequests",
    "PaymentLinks",
    "TransferDrafts",
    "WebhookEndpoints",
    "__version__",
    "transfer_authorization",
]
