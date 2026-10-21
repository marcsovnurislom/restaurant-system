from apps.orders.cart import Cart


def cart(request) -> dict:
    """Количество блюд в корзине для значка в шапке. Без запросов к БД."""
    return {"cart_count": Cart(request.session).count}
