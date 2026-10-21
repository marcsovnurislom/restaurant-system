from django.db.models import Prefetch, QuerySet

from apps.orders.models import Order, OrderStatusHistory


def order_queryset() -> QuerySet[Order]:
    """Заказы со всем, что нужно для показа: 3 запроса на любой размер списка."""
    return Order.objects.select_related("table").prefetch_related(
        "items",
        Prefetch("history", queryset=OrderStatusHistory.objects.order_by("changed_at", "pk")),
    )


def order_list_for(user) -> QuerySet[Order]:
    """Персонал видит все заказы, гость — только свои."""
    orders = order_queryset()
    if user.is_authenticated and user.is_staff_member:
        return orders
    if user.is_authenticated:
        return orders.filter(user=user)
    return orders.none()
