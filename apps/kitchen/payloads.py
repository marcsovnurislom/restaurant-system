"""Данные заказа, которые уходят в WebSocket.

Только простые типы (str, int, list, dict): слой Channels на Redis
сериализует сообщения через msgpack, Decimal и datetime он не понимает.
"""

from django.db.models import QuerySet
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.rules import TRANSITIONS, allowed_transitions
from apps.orders.selectors import order_queryset

Status = Order.Status

# Заказы, которые видны на экране кухни. Выполненные и отменённые исчезают.
ACTIVE_STATUSES = (Status.NEW, Status.CONFIRMED, Status.COOKING, Status.READY, Status.DELIVERING)

ACTION_LABELS = {
    Status.CONFIRMED: "Подтвердить",
    Status.COOKING: "Начать готовить",
    Status.READY: "Готово",
    Status.DELIVERING: "Отдать курьеру",
    Status.COMPLETED: "Выдан",
    Status.CANCELLED: "Отменить",
}


def active_orders() -> QuerySet[Order]:
    return order_queryset().filter(status__in=ACTIVE_STATUSES).order_by("created_at")


def kitchen_payload(order: Order) -> dict:
    """Карточка заказа для персонала, включая кнопки и роли, которым они доступны."""
    return {
        "id": order.pk,
        "status": order.status,
        "status_display": order.get_status_display(),
        "type": order.type,
        "type_display": order.get_type_display(),
        "table_number": order.table.number if order.table else None,
        "customer_name": order.customer_name,
        "address": order.address,
        "comment": order.comment,
        "payment_status": order.payment_status,
        "total": str(order.total),
        "created_at": order.created_at.isoformat(),
        "items": [
            {"name": item.dish_name, "quantity": item.quantity} for item in order.items.all()
        ],
        "actions": [
            {
                "status": target,
                "label": ACTION_LABELS[target],
                "roles": sorted(TRANSITIONS[order.status][target]),
            }
            for target in allowed_transitions(order)
        ],
    }


def guest_payload(order: Order) -> dict:
    """Что видит гость на странице заказа: без данных других гостей и без кнопок персонала."""
    return {
        "status": order.status,
        "status_display": order.get_status_display(),
        "payment_status": order.payment_status,
        "can_cancel": order.status == Status.NEW
        and order.payment_status != Order.PaymentStatus.PAID,
        "awaits_online_payment": order.awaits_online_payment,
        "history": [
            {
                "status": entry.to_status,
                "status_display": entry.get_to_status_display(),
                "time": f"{timezone.localtime(entry.changed_at):%H:%M}",
            }
            for entry in order.history.all()
        ],
    }
