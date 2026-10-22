"""Рассылка изменений заказа в открытые WebSocket-соединения."""

import logging
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.kitchen.payloads import guest_payload, kitchen_payload
from apps.orders.selectors import order_queryset

logger = logging.getLogger(__name__)

KITCHEN_GROUP = "kitchen"


def order_group(token: UUID) -> str:
    # Имя группы Channels: только латиница, цифры, - _ . и до 100 символов
    return f"order_{token.hex}"


def notify_order_changed(order_id: int) -> None:
    """Разослать заказ после коммита транзакции.

    on_commit: если транзакция откатится, экраны не покажут несуществующее изменение,
    а при рассылке до коммита другой процесс мог бы прочитать старые данные.
    robust=True: если Redis недоступен, заказ всё равно сохранится, ошибка уйдёт в лог.
    """

    # Обычная функция, а не functools.partial: при ошибке Django пишет в лог
    # callback.__qualname__, которого у partial нет, и сам падает с AttributeError
    def send() -> None:
        broadcast_order(order_id)

    transaction.on_commit(send, robust=True)


def broadcast_order(order_id: int) -> None:
    order = order_queryset().get(pk=order_id)
    send = async_to_sync(get_channel_layer().group_send)
    send(KITCHEN_GROUP, {"type": "order.updated", "order": kitchen_payload(order)})
    send(order_group(order.token), {"type": "order.updated", "order": guest_payload(order)})
    logger.debug("Заказ %s разослан: %s", order_id, order.status)
