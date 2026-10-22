from decimal import Decimal

import msgpack
import pytest

from apps.kitchen.payloads import active_orders, guest_payload, kitchen_payload
from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.selectors import order_queryset
from apps.orders.tests.factories import make_order

pytestmark = pytest.mark.django_db


def delivery_order() -> Order:
    order = make_order(
        dishes=[DishFactory(name="Лагман", price=Decimal("60000"))],
        order_type=Order.Type.DELIVERY,
        address="ул. Навои, 1",
        comment="Без лука",
    )
    return order_queryset().get(pk=order.pk)


def test_kitchen_payload():
    payload = kitchen_payload(delivery_order())

    assert payload["items"] == [{"name": "Лагман", "quantity": 1}]
    assert payload["address"] == "ул. Навои, 1"
    assert payload["comment"] == "Без лука"
    assert payload["total"] == "75000.00"
    assert [action["status"] for action in payload["actions"]] == ["confirmed", "cancelled"]
    assert payload["actions"][0]["roles"] == ["manager", "waiter"]


def test_payloads_are_msgpack_serializable():
    """Redis-слой Channels шлёт сообщения через msgpack: Decimal и datetime он бы не принял."""
    order = delivery_order()

    msgpack.packb(kitchen_payload(order))
    msgpack.packb(guest_payload(order))


def test_guest_payload_has_no_personal_data_or_staff_actions():
    payload = guest_payload(delivery_order())

    assert set(payload) == {
        "status",
        "status_display",
        "payment_status",
        "can_cancel",
        "awaits_online_payment",
        "history",
    }
    assert payload["can_cancel"] is True
    assert payload["history"][0]["status"] == "new"


def test_active_orders_exclude_finished():
    active = make_order()
    for status in (Order.Status.COMPLETED, Order.Status.CANCELLED):
        Order.objects.filter(pk=make_order().pk).update(status=status)

    assert list(active_orders()) == [active]
