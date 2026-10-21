"""Корзина сайта в сессии.

В сессии лежат только id блюд и количества. Цены всегда берутся из БД
при показе и при оформлении: цену из cookie или формы подделать нельзя.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.menu.models import Dish
from apps.orders.models import MAX_QUANTITY

SESSION_KEY = "cart"


@dataclass(frozen=True)
class CartLine:
    dish: Dish
    quantity: int

    @property
    def total(self) -> Decimal:
        return self.dish.price * self.quantity


class Cart:
    def __init__(self, session) -> None:
        self.session = session
        self.items: dict[str, int] = dict(session.get(SESSION_KEY, {}))

    def add(self, dish: Dish, quantity: int = 1) -> None:
        key = str(dish.pk)
        self.items[key] = min(self.items.get(key, 0) + quantity, MAX_QUANTITY)
        self._save()

    def set(self, dish: Dish, quantity: int) -> None:
        if quantity <= 0:
            self.remove(dish)
            return
        self.items[str(dish.pk)] = min(quantity, MAX_QUANTITY)
        self._save()

    def remove(self, dish: Dish) -> None:
        self.items.pop(str(dish.pk), None)
        self._save()

    def clear(self) -> None:
        self.items = {}
        self._save()

    @property
    def count(self) -> int:
        return sum(self.items.values())

    def lines(self) -> list[CartLine]:
        """Позиции с актуальными блюдами. Блюда из стоп-листа молча не показываются."""
        dishes = Dish.objects.available().in_bulk([int(key) for key in self.items])
        return [
            CartLine(dish=dishes[int(key)], quantity=quantity)
            for key, quantity in self.items.items()
            if int(key) in dishes
        ]

    def remove_unavailable(self) -> list[str]:
        """Убирает блюда, которые попали в стоп-лист. Возвращает их названия для сообщения."""
        ids = [int(key) for key in self.items]
        available = set(Dish.objects.available().filter(pk__in=ids).values_list("pk", flat=True))
        gone = [dish_id for dish_id in ids if dish_id not in available]
        if not gone:
            return []
        names = list(Dish.objects.filter(pk__in=gone).values_list("name", flat=True))
        for dish_id in gone:
            self.items.pop(str(dish_id))
        self._save()
        return names

    def as_order_items(self) -> list[tuple[int, int]]:
        return [(int(key), quantity) for key, quantity in self.items.items()]

    def _save(self) -> None:
        self.session[SESSION_KEY] = self.items
        self.session.modified = True
