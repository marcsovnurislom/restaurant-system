from datetime import timedelta

import pytest
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import order_mark_paid
from apps.orders.tasks import cancel_unpaid_orders
from apps.orders.tests.factories import make_order

pytestmark = pytest.mark.django_db


def created_minutes_ago(order: Order, minutes: int) -> Order:
    Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))
    order.refresh_from_db()
    return order


def online_order(minutes_ago: int) -> Order:
    return created_minutes_ago(make_order(payment_method=Order.PaymentMethod.ONLINE), minutes_ago)


def test_cancels_stale_unpaid_online_orders():
    stale = online_order(minutes_ago=20)
    fresh = online_order(minutes_ago=5)
    cash = created_minutes_ago(make_order(), minutes=60)
    paid = online_order(minutes_ago=60)
    order_mark_paid(order=paid)

    assert cancel_unpaid_orders() == 1

    for order in (stale, fresh, cash, paid):
        order.refresh_from_db()
    assert stale.status == Order.Status.CANCELLED
    assert stale.history.last().changed_by is None
    assert fresh.status == Order.Status.NEW
    assert cash.status == Order.Status.NEW
    assert paid.status == Order.Status.CONFIRMED


def test_is_idempotent():
    online_order(minutes_ago=30)

    assert cancel_unpaid_orders() == 1
    assert cancel_unpaid_orders() == 0
