import pytest

from apps.menu.selectors import dish_list, menu_by_category
from apps.menu.tests.factories import CategoryFactory, DishFactory, TagFactory

pytestmark = pytest.mark.django_db


def test_menu_hides_stop_list_inactive_and_empty_categories():
    soups = CategoryFactory(name="Супы")
    soup = DishFactory(category=soups)
    DishFactory(category=soups, is_available=False)
    DishFactory(category=CategoryFactory(is_active=False))
    DishFactory(category=CategoryFactory(name="Всё закончилось"), is_available=False)

    menu = menu_by_category()

    assert menu == [soups]
    assert menu[0].menu_dishes == [soup]


def test_menu_filter_by_tag():
    spicy = TagFactory(slug="ostroe")
    hot = DishFactory(tags=[spicy])
    DishFactory()

    menu = menu_by_category(tag_slug="ostroe")

    assert [dish for category in menu for dish in category.menu_dishes] == [hot]


def test_menu_query_count_does_not_grow_with_menu_size(django_assert_num_queries):
    tags = TagFactory.create_batch(2)
    for category in CategoryFactory.create_batch(4):
        DishFactory.create_batch(5, category=category, tags=tags)

    # категории + блюда + теги, без N+1
    with django_assert_num_queries(3):
        menu = menu_by_category()
        names = [tag.name for c in menu for d in c.menu_dishes for tag in d.tags.all()]

    assert len(names) == 4 * 5 * 2


def test_dish_list_for_staff_includes_stop_list():
    DishFactory()
    DishFactory(is_available=False)

    assert dish_list().count() == 1
    assert dish_list(include_unavailable=True).count() == 2
