import pytest

from apps.menu.tests.factories import DishFactory
from apps.orders.cart import SESSION_KEY, Cart
from apps.orders.models import MAX_QUANTITY

pytestmark = pytest.mark.django_db


class FakeSession(dict):
    modified = False


def test_add_and_count():
    session = FakeSession()
    plov, samsa = DishFactory(), DishFactory()
    cart = Cart(session)

    cart.add(plov)
    cart.add(plov, 2)
    cart.add(samsa)

    assert cart.count == 4
    assert session.modified
    # В сессии только id и количества — никаких цен
    assert session[SESSION_KEY] == {str(plov.pk): 3, str(samsa.pk): 1}


def test_quantity_is_capped():
    cart = Cart(FakeSession())
    dish = DishFactory()

    cart.add(dish, MAX_QUANTITY + 5)

    assert cart.count == MAX_QUANTITY


def test_set_zero_removes():
    cart = Cart(FakeSession())
    dish = DishFactory()
    cart.add(dish)

    cart.set(dish, 0)

    assert cart.count == 0


def test_lines_use_current_price_and_skip_stop_list():
    cart = Cart(FakeSession())
    available, gone = DishFactory(price=20000), DishFactory()
    cart.add(available, 2)
    cart.add(gone)
    available.price = 25000
    available.save()
    gone.is_available = False
    gone.save()

    lines = cart.lines()

    assert [(line.dish, line.quantity, line.total) for line in lines] == [(available, 2, 50000)]


def test_cart_survives_new_instance():
    session = FakeSession()
    dish = DishFactory()
    Cart(session).add(dish)

    assert Cart(session).as_order_items() == [(dish.pk, 1)]
