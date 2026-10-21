"""Stripe Checkout в тестовом режиме (ключи sk_test_... и whsec_...)."""

import json
from collections.abc import Mapping
from decimal import Decimal

import stripe
from django.conf import settings

from apps.payments.models import Payment
from apps.payments.providers.base import (
    CheckoutSession,
    InvalidWebhook,
    PaymentProvider,
    WebhookEvent,
)

# Суммы в Stripe передаются в минимальных единицах: 1 сум = 100 тийин
MINOR_UNITS = 100
CURRENCY = "uzs"


class StripeProvider(PaymentProvider):
    name = "stripe"

    def create_checkout(
        self, *, payment: Payment, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)
        session = client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": CURRENCY,
                            "unit_amount": int(payment.amount * MINOR_UNITS),
                            "product_data": {"name": f"Заказ №{payment.order_id}"},
                        },
                    }
                ],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": str(payment.order_id),
                "metadata": {"payment_id": str(payment.pk)},
            },
            # Повтор запроса с тем же ключом не создаст вторую сессию оплаты
            options={"idempotency_key": f"payment-{payment.pk}"},
        )
        return CheckoutSession(external_id=session.id, redirect_url=session.url)

    def parse_webhook(self, *, body: bytes, headers: Mapping[str, str]) -> WebhookEvent | None:
        try:
            event = stripe.Webhook.construct_event(
                body, headers.get("Stripe-Signature"), settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise InvalidWebhook(str(exc)) from exc

        if event["type"] not in ("checkout.session.completed", "checkout.session.expired"):
            return None

        session = event["data"]["object"]
        return WebhookEvent(
            external_id=session["id"],
            succeeded=(
                event["type"] == "checkout.session.completed"
                and session["payment_status"] == "paid"
            ),
            amount=Decimal(session["amount_total"]) / MINOR_UNITS,
            raw=json.loads(body),
        )
