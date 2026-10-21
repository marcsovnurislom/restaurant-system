from django.conf import settings

from apps.payments.providers.base import (
    CheckoutSession,
    InvalidWebhook,
    PaymentProvider,
    WebhookEvent,
)
from apps.payments.providers.fake import FakeProvider
from apps.payments.providers.stripe import StripeProvider

PROVIDERS: dict[str, type[PaymentProvider]] = {
    FakeProvider.name: FakeProvider,
    StripeProvider.name: StripeProvider,
}


class UnknownProvider(LookupError):
    pass


def get_provider(name: str | None = None) -> PaymentProvider:
    """Провайдер по имени, по умолчанию — из настройки PAYMENT_PROVIDER."""
    name = name or settings.PAYMENT_PROVIDER
    try:
        return PROVIDERS[name]()
    except KeyError as exc:
        raise UnknownProvider(name) from exc


__all__ = [
    "CheckoutSession",
    "InvalidWebhook",
    "PaymentProvider",
    "UnknownProvider",
    "WebhookEvent",
    "get_provider",
]
