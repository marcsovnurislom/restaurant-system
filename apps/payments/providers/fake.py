"""Тестовый провайдер для разработки: оплата без реальной платёжной системы.

Работает как настоящий провайдер: отдаёт ссылку на страницу оплаты и присылает
подписанный webhook. Поэтому весь путь оплаты проверяется локально, без ключей Stripe.
В продакшене включить его нельзя (см. config/settings/prod.py).
"""

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from apps.payments.models import Payment
from apps.payments.providers.base import (
    CheckoutSession,
    InvalidWebhook,
    PaymentProvider,
    WebhookEvent,
)

SIGNATURE_HEADER = "X-Fake-Signature"


class FakeProvider(PaymentProvider):
    name = "fake"

    def create_checkout(
        self, *, payment: Payment, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        external_id = f"fake_{uuid.uuid4().hex}"
        url = reverse("payments:fake-checkout", kwargs={"external_id": external_id})
        return CheckoutSession(external_id=external_id, redirect_url=url)

    def parse_webhook(self, *, body: bytes, headers: Mapping[str, str]) -> WebhookEvent | None:
        signature = headers.get(SIGNATURE_HEADER, "")
        # compare_digest сравнивает за постоянное время: подпись не подобрать по таймингам
        if not hmac.compare_digest(signature, self.sign(body)):
            raise InvalidWebhook("Неверная подпись")
        try:
            data = json.loads(body)
            return WebhookEvent(
                external_id=data["external_id"],
                succeeded=data["status"] == "succeeded",
                amount=Decimal(data["amount"]),
                raw=data,
            )
        except (ValueError, KeyError, ArithmeticError) as exc:
            raise InvalidWebhook("Испорченное тело запроса") from exc

    @staticmethod
    def sign(body: bytes) -> str:
        secret = settings.PAYMENTS_FAKE_SECRET.encode()
        return hmac.new(secret, body, hashlib.sha256).hexdigest()

    @classmethod
    def build_webhook(
        cls, *, external_id: str, succeeded: bool, amount: Decimal
    ) -> tuple[bytes, dict[str, str]]:
        """Тело и заголовки webhook — так, как их прислал бы провайдер."""
        body = json.dumps(
            {
                "external_id": external_id,
                "status": "succeeded" if succeeded else "failed",
                "amount": str(amount),
            }
        ).encode()
        return body, {SIGNATURE_HEADER: cls.sign(body)}
