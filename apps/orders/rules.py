"""Правила заказов: доставка и разрешённые переходы статусов."""

from datetime import timedelta
from decimal import Decimal

from apps.core.errors import DomainError
from apps.orders.models import Order
from apps.users.models import User

DELIVERY_FEE = Decimal("15000")
FREE_DELIVERY_FROM = Decimal("150000")
MIN_DELIVERY_ORDER = Decimal("50000")
# Сколько ждём онлайн-оплату, прежде чем отменить заказ и освободить кухню
UNPAID_ORDER_TTL = timedelta(minutes=15)

Status = Order.Status
Role = User.Role

# State machine: из какого статуса в какой можно перейти и какие роли это делают.
# Администратор проходит любую проверку роли (User.has_role).
TRANSITIONS: dict[str, dict[str, frozenset[str]]] = {
    Status.NEW: {
        Status.CONFIRMED: frozenset({Role.MANAGER, Role.WAITER}),
        Status.CANCELLED: frozenset({Role.MANAGER, Role.WAITER}),
    },
    Status.CONFIRMED: {
        Status.COOKING: frozenset({Role.COOK, Role.MANAGER}),
        Status.CANCELLED: frozenset({Role.MANAGER}),
    },
    Status.COOKING: {
        Status.READY: frozenset({Role.COOK, Role.MANAGER}),
    },
    Status.READY: {
        Status.DELIVERING: frozenset({Role.COURIER, Role.MANAGER}),
        Status.COMPLETED: frozenset({Role.WAITER, Role.MANAGER}),
    },
    Status.DELIVERING: {
        Status.COMPLETED: frozenset({Role.COURIER, Role.MANAGER}),
    },
}


class OrderError(DomainError):
    # Блюдо закончилось, пока гость оформлял заказ — 409
    conflict_codes = frozenset({"unavailable"})


def delivery_fee_for(order_type: str, items_total: Decimal) -> Decimal:
    if order_type != Order.Type.DELIVERY or items_total >= FREE_DELIVERY_FROM:
        return Decimal("0")
    return DELIVERY_FEE


def allowed_transitions(order: Order) -> list[str]:
    """Куда можно перевести заказ с учётом его типа (без проверки ролей)."""
    targets = []
    for target in TRANSITIONS.get(order.status, {}):
        try:
            check_transition_for_type(order, target)
        except OrderError:
            continue
        targets.append(target)
    return targets


def check_transition_for_type(order: Order, target: str) -> None:
    is_delivery = order.type == Order.Type.DELIVERY
    if target == Status.DELIVERING and not is_delivery:
        raise OrderError("Передать курьеру можно только заказ на доставку.", "invalid_transition")
    if order.status == Status.READY and target == Status.COMPLETED and is_delivery:
        raise OrderError("Заказ на доставку завершает курьер.", "invalid_transition")
    if target == Status.CONFIRMED and order.awaits_online_payment:
        raise OrderError("Заказ ещё не оплачен онлайн.", "awaiting_payment")
