import logging
from collections import Counter
from collections.abc import Iterable

from django.db import transaction

from apps.menu.models import Dish
from apps.menu.templatetags.money import money
from apps.orders.models import MAX_QUANTITY, Order, OrderItem, OrderStatusHistory
from apps.orders.rules import (
    MIN_DELIVERY_ORDER,
    TRANSITIONS,
    OrderError,
    check_transition_for_type,
    delivery_fee_for,
)
from apps.tables.models import Table

logger = logging.getLogger(__name__)


def order_create(
    *,
    items: Iterable[tuple[int, int]],
    order_type: str,
    customer_name: str,
    phone: str,
    payment_method: str,
    address: str = "",
    comment: str = "",
    table: Table | None = None,
    user=None,
) -> Order:
    """Создаёт заказ из пар (id блюда, количество).

    Цены берутся из БД в момент заказа и копируются в OrderItem.
    Всё создаётся в одной транзакции: заказ без позиций или истории невозможен.
    """
    quantities: Counter[int] = Counter()
    for dish_id, quantity in items:
        quantities[dish_id] += quantity
    if not quantities:
        raise OrderError("Корзина пуста.", "empty")
    if any(not 1 <= quantity <= MAX_QUANTITY for quantity in quantities.values()):
        raise OrderError(f"Можно заказать от 1 до {MAX_QUANTITY} порций блюда.", "invalid_quantity")

    address = address.strip()
    if order_type == Order.Type.DELIVERY and not address:
        raise OrderError("Укажите адрес доставки.", "address_required")
    if order_type == Order.Type.DINE_IN and table is None:
        raise OrderError("Заказ в зале оформляется по QR-коду на столе.", "table_required")
    if order_type != Order.Type.DINE_IN:
        table = None
    if order_type != Order.Type.DELIVERY:
        address = ""

    dishes = Dish.objects.available().in_bulk(list(quantities))
    missing = [dish_id for dish_id in quantities if dish_id not in dishes]
    if missing:
        names = ", ".join(Dish.objects.filter(pk__in=missing).values_list("name", flat=True))
        raise OrderError(
            f"Эти блюда закончились: {names or 'неизвестные блюда'}. Уберите их из заказа.",
            "unavailable",
        )

    items_total = sum(dishes[dish_id].price * qty for dish_id, qty in quantities.items())
    if order_type == Order.Type.DELIVERY and items_total < MIN_DELIVERY_ORDER:
        raise OrderError(
            f"Минимальная сумма заказа на доставку — {money(MIN_DELIVERY_ORDER)}.", "min_order"
        )
    delivery_fee = delivery_fee_for(order_type, items_total)

    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            table=table,
            type=order_type,
            payment_method=payment_method,
            customer_name=customer_name,
            phone=phone,
            address=address,
            comment=comment,
            items_total=items_total,
            delivery_fee=delivery_fee,
            total=items_total + delivery_fee,
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                dish=dishes[dish_id],
                dish_name=dishes[dish_id].name,
                unit_price=dishes[dish_id].price,
                quantity=quantity,
            )
            for dish_id, quantity in quantities.items()
        )
        OrderStatusHistory.objects.create(order=order, to_status=Order.Status.NEW, changed_by=user)

    logger.info("Заказ %s создан: %s, %s сум", order.pk, order_type, order.total)
    return order


def order_transition(*, order: Order, to_status: str, by_user) -> Order:
    """Переводит заказ в новый статус по правилам state machine (rules.TRANSITIONS)."""
    with transaction.atomic():
        # Блокировка строки: два сотрудника не переведут один заказ одновременно
        order = Order.objects.select_for_update().get(pk=order.pk)
        targets = TRANSITIONS.get(order.status, {})
        if to_status not in targets:
            target_label = (
                Order.Status(to_status).label if to_status in Order.Status.values else to_status
            )
            raise OrderError(
                f"Нельзя перевести заказ из «{order.get_status_display()}» в «{target_label}».",
                "invalid_transition",
            )
        if not by_user.has_role(*targets[to_status]):
            raise OrderError("У вашей роли нет права на это действие.", "forbidden")
        check_transition_for_type(order, to_status)
        _set_status(order, to_status, changed_by=by_user)
    return order


def order_cancel_by_customer(*, order: Order) -> Order:
    """Гость отменяет заказ сам, пока его не подтвердили и не оплатили."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.NEW:
            raise OrderError(
                "Заказ уже принят в работу. Отменить его можно по телефону.", "too_late"
            )
        if order.payment_status == Order.PaymentStatus.PAID:
            raise OrderError("Оплаченный заказ отменяется по телефону.", "already_paid")
        _set_status(order, Order.Status.CANCELLED, changed_by=None)
    return order


def order_mark_paid(*, order: Order) -> Order:
    """Онлайн-оплата прошла: заказ оплачен и сразу подтверждён.

    Идемпотентна: повторный webhook от провайдера ничего не изменит.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == Order.PaymentStatus.PAID:
            return order
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        if order.status == Order.Status.NEW:
            _set_status(order, Order.Status.CONFIRMED, changed_by=None)
        else:
            # Например, менеджер отменил заказ, пока гость был на странице оплаты
            logger.warning(
                "Заказ %s оплачен в статусе %s: нужен возврат денег", order.pk, order.status
            )
    return order


def _set_status(order: Order, to_status: str, *, changed_by) -> None:
    from_status = order.status
    order.status = to_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusHistory.objects.create(
        order=order, from_status=from_status, to_status=to_status, changed_by=changed_by
    )
    logger.info("Заказ %s: %s → %s", order.pk, from_status, to_status)
