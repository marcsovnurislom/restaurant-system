import hashlib
import hmac
import json
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.payments.models import Payment
from apps.payments.providers.fake import FakeProvider
from apps.payments.providers.stripe import StripeProvider
from apps.payments.services import payment_start

pytestmark = pytest.mark.django_db


def online_order() -> Order:
    return make_order(
        dishes=[DishFactory(price=Decimal("45000"))], payment_method=Order.PaymentMethod.ONLINE
    )


def webhook_url(provider: str) -> str:
    return reverse("payments-api:webhook", kwargs={"provider": provider})


def send_fake_webhook(api_client, payment, *, succeeded=True, amount=None):
    body, headers = FakeProvider.build_webhook(
        external_id=payment.external_id,
        succeeded=succeeded,
        amount=payment.amount if amount is None else amount,
    )
    return api_client.post(
        webhook_url("fake"),
        data=body,
        content_type="application/json",
        headers=headers,
    )


@pytest.fixture
def started_payment():
    order = online_order()
    payment_start(order=order)
    return Payment.objects.get(order=order)


class TestCheckout:
    def test_creates_pending_payment(self, api_client):
        order = online_order()

        response = api_client.post(reverse("payments-api:checkout", kwargs={"token": order.token}))

        payment = Payment.objects.get()
        assert response.status_code == 201
        assert response.data["redirect_url"].startswith("/payments/fake/")
        assert payment.status == Payment.Status.PENDING
        assert payment.amount == order.total
        assert payment.external_id.startswith("fake_")

    def test_cash_order(self, api_client):
        order = make_order()

        response = api_client.post(reverse("payments-api:checkout", kwargs={"token": order.token}))

        assert response.status_code == 400

    def test_already_paid(self, api_client, started_payment):
        send_fake_webhook(api_client, started_payment)

        response = api_client.post(
            reverse("payments-api:checkout", kwargs={"token": started_payment.order.token})
        )

        assert response.status_code == 400


class TestFakeWebhook:
    def test_success_marks_order_paid(self, api_client, started_payment):
        response = send_fake_webhook(api_client, started_payment)

        started_payment.refresh_from_db()
        order = started_payment.order
        order.refresh_from_db()
        assert response.status_code == 200
        assert started_payment.status == Payment.Status.SUCCEEDED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED

    def test_forged_signature_is_rejected(self, api_client, started_payment):
        body, _ = FakeProvider.build_webhook(
            external_id=started_payment.external_id, succeeded=True, amount=started_payment.amount
        )

        response = api_client.post(
            webhook_url("fake"),
            data=body,
            content_type="application/json",
            headers={"X-Fake-Signature": "0" * 64},
        )

        started_payment.refresh_from_db()
        assert response.status_code == 400
        assert started_payment.status == Payment.Status.PENDING

    def test_repeated_webhook_is_idempotent(self, api_client, started_payment):
        send_fake_webhook(api_client, started_payment)
        send_fake_webhook(api_client, started_payment)

        assert started_payment.order.history.count() == 2

    def test_wrong_amount_is_not_accepted(self, api_client, started_payment):
        send_fake_webhook(api_client, started_payment, amount=Decimal("1"))

        started_payment.refresh_from_db()
        assert started_payment.status == Payment.Status.FAILED
        assert started_payment.order.payment_status == Order.PaymentStatus.UNPAID

    def test_declined_payment(self, api_client, started_payment):
        send_fake_webhook(api_client, started_payment, succeeded=False)

        started_payment.refresh_from_db()
        assert started_payment.status == Payment.Status.FAILED
        assert started_payment.order.status == Order.Status.NEW

    def test_unknown_payment_is_ignored(self, api_client):
        body, headers = FakeProvider.build_webhook(
            external_id="fake_unknown", succeeded=True, amount=Decimal("1")
        )

        response = api_client.post(
            webhook_url("fake"), data=body, content_type="application/json", headers=headers
        )

        assert response.status_code == 200

    def test_unknown_provider(self, api_client):
        response = api_client.post(
            webhook_url("paypal"), data=b"{}", content_type="application/json"
        )

        assert response.status_code == 404


def stripe_signature(payload: bytes, secret: str) -> str:
    """Заголовок Stripe-Signature, как его формирует Stripe."""
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class TestStripe:
    @pytest.fixture
    def stripe_payment(self):
        order = online_order()
        return Payment.objects.create(
            order=order, provider="stripe", external_id="cs_test_123", amount=order.total
        )

    def event(self, payment, event_type="checkout.session.completed", amount=None) -> bytes:
        amount = payment.amount if amount is None else amount
        return json.dumps(
            {
                "id": "evt_test",
                "object": "event",
                "type": event_type,
                "data": {
                    "object": {
                        "id": payment.external_id,
                        "object": "checkout.session",
                        "payment_status": "paid",
                        "amount_total": int(amount * 100),
                    }
                },
            }
        ).encode()

    def post(self, api_client, body: bytes, signature: str):
        return api_client.post(
            webhook_url("stripe"),
            data=body,
            content_type="application/json",
            headers={"Stripe-Signature": signature},
        )

    def test_signed_webhook_marks_paid(self, api_client, settings, stripe_payment):
        body = self.event(stripe_payment)

        response = self.post(
            api_client, body, stripe_signature(body, settings.STRIPE_WEBHOOK_SECRET)
        )

        stripe_payment.order.refresh_from_db()
        assert response.status_code == 200
        assert stripe_payment.order.payment_status == Order.PaymentStatus.PAID

    def test_wrong_secret_is_rejected(self, api_client, stripe_payment):
        body = self.event(stripe_payment)

        response = self.post(api_client, body, stripe_signature(body, "whsec_attacker"))

        assert response.status_code == 400

    def test_other_events_are_ignored(self, api_client, settings, stripe_payment):
        body = self.event(stripe_payment, event_type="payment_intent.created")

        self.post(api_client, body, stripe_signature(body, settings.STRIPE_WEBHOOK_SECRET))

        stripe_payment.refresh_from_db()
        assert stripe_payment.status == Payment.Status.PENDING

    def test_create_checkout_sends_amount_in_minor_units(self, monkeypatch, stripe_payment):
        calls = {}

        class FakeSessions:
            def create(self, params, options):
                calls.update(params=params, options=options)
                return SimpleNamespace(id="cs_test_new", url="https://checkout.stripe.com/x")

        fake_client = SimpleNamespace(
            v1=SimpleNamespace(checkout=SimpleNamespace(sessions=FakeSessions()))
        )
        monkeypatch.setattr("stripe.StripeClient", lambda api_key: fake_client)

        session = StripeProvider().create_checkout(
            payment=stripe_payment, success_url="https://x/ok", cancel_url="https://x/no"
        )

        price = calls["params"]["line_items"][0]["price_data"]
        assert session.external_id == "cs_test_new"
        assert price["currency"] == "uzs"
        assert price["unit_amount"] == int(stripe_payment.amount * 100)
        assert calls["options"]["idempotency_key"] == f"payment-{stripe_payment.pk}"


def test_fake_checkout_page_hidden_when_stripe(client, settings, started_payment):
    settings.PAYMENT_PROVIDER = "stripe"

    url = reverse("payments:fake-checkout", kwargs={"external_id": started_payment.external_id})

    assert client.get(url).status_code == 404
