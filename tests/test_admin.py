"""Smoke-тест админки: списки и формы открываются без ошибок."""

import pytest
from django.urls import reverse

from apps.menu.models import Dish
from apps.menu.tests.factories import DishFactory, TagFactory
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.payments.services import payment_start
from apps.reservations.tests.factories import ReservationFactory
from apps.tables.tests.factories import TableFactory
from apps.users.models import User

pytestmark = pytest.mark.django_db

MODELS = [
    "users_user",
    "menu_category",
    "menu_tag",
    "menu_dish",
    "tables_table",
    "reservations_reservation",
]
# Заказы и платежи в админке только для просмотра: страницы добавления нет
READ_ONLY_MODELS = ["orders_order", "payments_payment"]


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser("admin", "admin@example.com", "x")
    client.force_login(admin)
    DishFactory(tags=[TagFactory()])
    ReservationFactory(table=TableFactory())
    return client


@pytest.mark.parametrize("model", MODELS)
def test_changelist_and_add_pages(admin_client, model):
    assert admin_client.get(reverse(f"admin:{model}_changelist")).status_code == 200
    assert admin_client.get(reverse(f"admin:{model}_add")).status_code == 200


@pytest.mark.parametrize("model", READ_ONLY_MODELS)
def test_read_only_admin(admin_client, model):
    order = make_order(payment_method=Order.PaymentMethod.ONLINE)
    payment_start(order=order)
    obj_id = order.pk if model == "orders_order" else order.payments.get().pk

    assert admin_client.get(reverse(f"admin:{model}_changelist")).status_code == 200
    assert admin_client.get(reverse(f"admin:{model}_change", args=[obj_id])).status_code == 200
    assert admin_client.get(reverse(f"admin:{model}_add")).status_code == 403


def test_stop_list_action(admin_client):
    dish = Dish.objects.get()

    admin_client.post(
        reverse("admin:menu_dish_changelist"),
        {"action": "put_on_stop_list", "_selected_action": [dish.pk]},
    )

    dish.refresh_from_db()
    assert not dish.is_available
