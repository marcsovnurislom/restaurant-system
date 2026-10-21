from decimal import Decimal

import pytest

from apps.orders.models import Order
from apps.orders.rules import allowed_transitions, delivery_fee_for

Status = Order.Status


@pytest.mark.parametrize(
    ("order_type", "items_total", "expected"),
    [
        (Order.Type.DELIVERY, Decimal("100000"), Decimal("15000")),
        (Order.Type.DELIVERY, Decimal("150000"), Decimal("0")),
        (Order.Type.PICKUP, Decimal("10000"), Decimal("0")),
        (Order.Type.DINE_IN, Decimal("10000"), Decimal("0")),
    ],
)
def test_delivery_fee(order_type, items_total, expected):
    assert delivery_fee_for(order_type, items_total) == expected


@pytest.mark.parametrize(
    ("order_type", "status", "expected"),
    [
        (Order.Type.DELIVERY, Status.READY, [Status.DELIVERING]),
        (Order.Type.PICKUP, Status.READY, [Status.COMPLETED]),
        (Order.Type.DINE_IN, Status.COOKING, [Status.READY]),
        (Order.Type.PICKUP, Status.COMPLETED, []),
        (Order.Type.PICKUP, Status.CANCELLED, []),
    ],
)
def test_allowed_transitions(order_type, status, expected):
    order = Order(type=order_type, status=status, payment_method=Order.PaymentMethod.CASH)

    assert allowed_transitions(order) == expected


def test_unpaid_online_order_cannot_be_confirmed():
    order = Order(
        type=Order.Type.PICKUP,
        status=Status.NEW,
        payment_method=Order.PaymentMethod.ONLINE,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    assert allowed_transitions(order) == [Status.CANCELLED]
