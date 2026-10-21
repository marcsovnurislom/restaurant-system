from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.menu.models import Dish
from apps.menu.tests.factories import CategoryFactory, DishFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-100")])
def test_price_must_be_positive_at_db_level(price):
    # save() не вызывает валидаторы, поэтому срабатывает CHECK constraint в БД
    with pytest.raises(IntegrityError):
        DishFactory(price=price)


def test_category_with_dishes_cannot_be_deleted():
    dish = DishFactory()

    with pytest.raises(ProtectedError):
        dish.category.delete()


def test_available_excludes_stop_list_and_inactive_categories():
    visible = DishFactory()
    DishFactory(is_available=False)
    DishFactory(category=CategoryFactory(is_active=False))

    assert list(Dish.objects.available()) == [visible]
