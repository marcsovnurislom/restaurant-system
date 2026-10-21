"""Smoke-тест админки: списки и формы открываются без ошибок."""

import pytest
from django.urls import reverse

from apps.menu.models import Dish
from apps.menu.tests.factories import DishFactory, TagFactory
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


def test_stop_list_action(admin_client):
    dish = Dish.objects.get()

    admin_client.post(
        reverse("admin:menu_dish_changelist"),
        {"action": "put_on_stop_list", "_selected_action": [dish.pk]},
    )

    dish.refresh_from_db()
    assert not dish.is_available
