"""Страницы сайта для гостей."""

import uuid
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.menu.templatetags.money import money
from apps.menu.tests.factories import DishFactory, TagFactory
from apps.menu.views import TABLE_SESSION_KEY
from apps.tables.tests.factories import TableFactory

pytestmark = pytest.mark.django_db


def test_home_shows_hits(client):
    hit = DishFactory(name="Плов свадебный", tags=[TagFactory(slug="hit")])
    DishFactory(name="Лагман")

    response = client.get(reverse("menu:home"))

    assert response.status_code == 200
    assert list(response.context["featured"]) == [hit]


def test_home_without_hits_shows_any_dishes(client):
    DishFactory(name="Лагман")

    response = client.get(reverse("menu:home"))

    assert "Лагман" in response.content.decode()


def test_menu_page(client, django_assert_num_queries):
    DishFactory(name="Шурпа")
    DishFactory(name="Закончилось", is_available=False)

    # теги для фильтра + категории + блюда + теги блюд
    with django_assert_num_queries(4):
        response = client.get(reverse("menu:menu-list"))

    html = response.content.decode()
    assert response.status_code == 200
    assert "Шурпа" in html
    assert "Закончилось" not in html


def test_menu_page_tag_filter(client):
    DishFactory(name="Лагман", tags=[TagFactory(slug="ostroe")])
    DishFactory(name="Айран")

    html = client.get(reverse("menu:menu-list"), {"tag": "ostroe"}).content.decode()

    assert "Лагман" in html
    assert "Айран" not in html


def test_dish_detail(client):
    dish = DishFactory(name="Самса", price=Decimal("12000"))

    response = client.get(reverse("menu:dish-detail", kwargs={"slug": dish.slug}))

    assert response.status_code == 200
    assert "12 000 сум" in response.content.decode()


def test_stop_listed_dish_page_is_404(client):
    dish = DishFactory(is_available=False)

    response = client.get(reverse("menu:dish-detail", kwargs={"slug": dish.slug}))

    assert response.status_code == 404


class TestTableMenu:
    def test_opens_menu_and_remembers_table(self, client):
        table = TableFactory(number=7)
        DishFactory(name="Шурпа")

        response = client.get(table.get_absolute_url())

        assert response.status_code == 200
        assert "№7" in response.content.decode()
        assert client.session[TABLE_SESSION_KEY] == table.pk

    def test_inactive_table_is_404(self, client):
        table = TableFactory(is_active=False)

        assert client.get(table.get_absolute_url()).status_code == 404

    def test_unknown_token_is_404(self, client):
        url = reverse("menu:table-menu", kwargs={"token": uuid.uuid4()})

        assert client.get(url).status_code == 404


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("45000.00"), "45 000 сум"),
        (Decimal("1234567.50"), "1 234 568 сум"),
        (900, "900 сум"),
        (None, ""),
        ("abc", ""),
    ],
)
def test_money_filter(value, expected):
    assert money(value) == expected
