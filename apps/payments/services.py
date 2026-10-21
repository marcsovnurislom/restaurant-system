import logging
from collections.abc import Mapping

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from apps.core.errors import DomainError
from apps.orders.models import Order
from apps.orders.services import order_mark_paid
from apps.payments.models import Payment
from apps.payments.providers import CheckoutSession, get_provider

logger = logging.getLogger(__name__)


class PaymentError(DomainError):
    pass


def payment_start(*, order: Order) -> CheckoutSession:
    """Создаёт платёж и страницу оплаты у провайдера."""
    if order.payment_method != Order.PaymentMethod.ONLINE:
        raise PaymentError("Этот заказ оплачивается при получении.", "not_online")
    if order.payment_status == Order.PaymentStatus.PAID:
        raise PaymentError("Заказ уже оплачен.", "already_paid")
    if order.status != Order.Status.NEW:
        raise PaymentError("Этот заказ уже нельзя оплатить онлайн.", "not_payable")

    provider = get_provider()
    payment = Payment.objects.create(order=order, provider=provider.name, amount=order.total)
    order_url = f"{settings.SITE_URL.rstrip('/')}{order_page_path(order)}"
    session = provider.create_checkout(payment=payment, success_url=order_url, cancel_url=order_url)
    payment.external_id = session.external_id
    payment.save(update_fields=["external_id", "updated_at"])
    logger.info("Платёж %s за заказ %s создан у %s", payment.pk, order.pk, provider.name)
    return session


def payment_process_webhook(
    *, provider_name: str, body: bytes, headers: Mapping[str, str]
) -> Payment | None:
    """Обрабатывает уведомление провайдера об оплате.

    - Подпись проверяет провайдер: подделанный webhook не отметит заказ оплаченным.
    - Идемпотентно: провайдеры повторяют webhook, пока не получат 200, поэтому
      повторное уведомление по уже обработанному платежу ничего не меняет.
    - Сумма сверяется с ожидаемой: оплата не той суммы не засчитывается.
    """
    provider = get_provider(provider_name)
    event = provider.parse_webhook(body=body, headers=headers)
    if event is None:
        return None

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .select_related("order")
            .filter(provider=provider.name, external_id=event.external_id)
            .first()
        )
        if payment is None:
            logger.warning("Webhook для неизвестного платежа %s", event.external_id)
            return None
        if payment.status != Payment.Status.PENDING:
            return payment

        payment.raw_payload = event.raw
        if event.succeeded and event.amount == payment.amount:
            payment.status = Payment.Status.SUCCEEDED
        else:
            if event.succeeded:
                logger.error(
                    "Платёж %s: оплачено %s вместо %s", payment.pk, event.amount, payment.amount
                )
            payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "raw_payload", "updated_at"])

        if payment.status == Payment.Status.SUCCEEDED:
            order_mark_paid(order=payment.order)
    return payment


def order_page_path(order: Order) -> str:
    return reverse("orders:detail", kwargs={"token": order.token})
