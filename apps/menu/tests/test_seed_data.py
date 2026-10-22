from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.menu.management.commands.seed_data import DEFAULT_STAFF_PASSWORD, DISHES, TABLES
from apps.menu.models import Category, Dish, Tag
from apps.orders.models import Order
from apps.tables.models import Table
from apps.users.models import User

pytestmark = pytest.mark.django_db


def run_seed(*args) -> str:
    out = StringIO()
    call_command("seed_data", *args, stdout=out)
    return out.getvalue()


def test_seed_is_idempotent():
    run_seed()
    run_seed()

    assert Dish.objects.count() == len(DISHES)
    assert Table.objects.count() == len(TABLES)
    assert Category.objects.count() == 6
    assert Tag.objects.count() == 4
    assert Dish.objects.get(slug="lagman").tags.count() == 2


def test_seed_keeps_stop_list():
    run_seed()
    Dish.objects.filter(slug="lagman").update(is_available=False)

    run_seed()

    assert not Dish.objects.get(slug="lagman").is_available


def test_seed_without_flag_creates_no_users():
    run_seed()

    assert not User.objects.exists()


def test_seed_demo_orders_are_recreated():
    run_seed("--with-orders", "20")
    run_seed("--with-orders", "20")

    orders = Order.objects.all()
    assert orders.count() == 20
    for order in orders.prefetch_related("items"):
        items_total = sum(item.unit_price * item.quantity for item in order.items.all())
        assert order.items_total == items_total
        assert order.total == items_total + order.delivery_fee
    assert orders.filter(created_at__date__lt=timezone.localdate()).exists()


def test_seed_staff():
    first = run_seed("--with-staff")
    second = run_seed("--with-staff")

    cook = User.objects.get(username="demo_cook")
    assert cook.role == User.Role.COOK
    assert cook.check_password(DEFAULT_STAFF_PASSWORD)
    assert "новых сотрудников: 4" in first
    assert "новых сотрудников: 0" in second
