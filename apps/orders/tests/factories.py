from decimal import Decimal

from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.services import order_create


def make_order(*, dishes=None, **kwargs) -> Order:
    """Заказ через настоящий сервис: суммы и позиции всегда согласованы."""
    dishes = dishes or [DishFactory(price=Decimal("30000"))]
    params = {
        "order_type": Order.Type.PICKUP,
        "customer_name": "Нодира",
        "phone": "+998935554433",
        "payment_method": Order.PaymentMethod.CASH,
    }
    params.update(kwargs)
    return order_create(items=[(dish.pk, 1) for dish in dishes], **params)
