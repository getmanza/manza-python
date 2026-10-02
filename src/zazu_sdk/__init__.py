"""Zazu Python SDK. Mirrors lib/zazu.rb."""

from . import transfer_authorization
from ._version import __version__
from .client import Zazu
from .errors import (
    ZazuArgumentError,
    ZazuAuthenticationError,
    ZazuConfigurationError,
    ZazuConflictError,
    ZazuConnectionError,
    ZazuError,
    ZazuForbiddenError,
    ZazuNotFoundError,
    ZazuRateLimitError,
    ZazuServerError,
    ZazuValidationError,
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
from .response import ZazuResponse

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
    "Page",
    "PayeeTrustRequests",
    "PaymentLinks",
    "TransferDrafts",
    "WebhookEndpoints",
    "Zazu",
    "ZazuArgumentError",
    "ZazuAuthenticationError",
    "ZazuConfigurationError",
    "ZazuConflictError",
    "ZazuConnectionError",
    "ZazuError",
    "ZazuForbiddenError",
    "ZazuNotFoundError",
    "ZazuRateLimitError",
    "ZazuResponse",
    "ZazuServerError",
    "ZazuValidationError",
    "__version__",
    "transfer_authorization",
]
