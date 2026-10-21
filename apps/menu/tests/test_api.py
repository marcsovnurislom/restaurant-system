import pytest
from django.urls import reverse

from apps.menu.models import Category, Dish
from apps.menu.tests.factories import CategoryFactory, DishFactory, TagFactory
from apps.users.models import User

pytestmark = pytest.mark.django_db

DISHES_URL = reverse("menu-api:dish-list")
CATEGORIES_URL = reverse("menu-api:category-list")


def dish_url(dish: Dish) -> str:
    return reverse("menu-api:dish-detail", kwargs={"slug": dish.slug})


def availability_url(dish: Dish) -> str:
    return reverse("menu-api:dish-availability", kwargs={"slug": dish.slug})


def slugs(response) -> set[str]:
    return {item["slug"] for item in response.data["results"]}


class TestDishList:
    def test_guest_sees_only_available(self, api_client):
        visible = DishFactory()
        DishFactory(is_available=False)
        DishFactory(category=CategoryFactory(is_active=False))

        response = api_client.get(DISHES_URL)

        assert response.status_code == 200
        assert slugs(response) == {visible.slug}

    def test_staff_sees_stop_list(self, client_for):
        DishFactory()
        DishFactory(is_available=False)

        response = client_for(User.Role.COOK).get(DISHES_URL)

        assert response.data["count"] == 2

    def test_filter_by_category(self, api_client):
        soup = DishFactory(category=CategoryFactory(slug="supy"))
        DishFactory()

        response = api_client.get(DISHES_URL, {"category": "supy"})

        assert slugs(response) == {soup.slug}

    def test_filter_by_tag_has_no_duplicates(self, api_client):
        spicy, hit = TagFactory(slug="ostroe"), TagFactory(slug="hit")
        both = DishFactory(tags=[spicy, hit])
        DishFactory(tags=[hit])

        response = api_client.get(DISHES_URL, {"tag": "ostroe"})

        assert response.data["count"] == 1
        assert slugs(response) == {both.slug}

    def test_filter_by_price_range(self, api_client):
        DishFactory(price=10000)
        middle = DishFactory(price=30000)
        DishFactory(price=90000)

        response = api_client.get(DISHES_URL, {"price_min": 20000, "price_max": 50000})

        assert slugs(response) == {middle.slug}

    def test_search(self, api_client):
        plov = DishFactory(name="Плов свадебный")
        DishFactory(name="Лагман")

        # Подстрока в нижнем регистре: SQLite не умеет регистронезависимо для кириллицы
        response = api_client.get(DISHES_URL, {"search": "свадеб"})

        assert slugs(response) == {plov.slug}

    def test_query_count_is_constant(self, api_client, django_assert_num_queries):
        tags = TagFactory.create_batch(3)
        DishFactory.create_batch(15, tags=tags)

        # COUNT для пагинации + блюда с категориями + теги
        with django_assert_num_queries(3):
            response = api_client.get(DISHES_URL)

        assert len(response.data["results"]) == 15


class TestDishWrite:
    @pytest.fixture
    def payload(self):
        CategoryFactory(slug="supy")
        TagFactory(slug="hit")
        return {
            "name": "Шурпа",
            "slug": "shurpa",
            "price": "38000.00",
            "weight_g": 400,
            "category": "supy",
            "tags": ["hit"],
        }

    def test_manager_creates_dish(self, client_for, payload):
        response = client_for(User.Role.MANAGER).post(DISHES_URL, payload, format="json")

        assert response.status_code == 201
        dish = Dish.objects.get(slug="shurpa")
        assert dish.category.slug == "supy"
        assert list(dish.tags.values_list("slug", flat=True)) == ["hit"]

    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.COOK, User.Role.WAITER])
    def test_others_cannot_create(self, client_for, payload, role):
        response = client_for(role).post(DISHES_URL, payload, format="json")

        assert response.status_code == 403

    def test_anonymous_cannot_create(self, api_client, payload):
        assert api_client.post(DISHES_URL, payload, format="json").status_code == 401

    def test_zero_price_is_validation_error(self, client_for, payload):
        response = client_for(User.Role.MANAGER).post(
            DISHES_URL, {**payload, "price": "0"}, format="json"
        )

        assert response.status_code == 400
        assert "price" in response.data

    def test_unknown_category(self, client_for, payload):
        response = client_for(User.Role.MANAGER).post(
            DISHES_URL, {**payload, "category": "net-takoy"}, format="json"
        )

        assert response.status_code == 400
        assert "category" in response.data


class TestStopList:
    @pytest.mark.parametrize("role", [User.Role.COOK, User.Role.MANAGER])
    def test_cook_and_manager_toggle_availability(self, client_for, role):
        dish = DishFactory()

        response = client_for(role).patch(availability_url(dish), {"is_available": False})

        assert response.status_code == 200
        assert response.data["is_available"] is False
        dish.refresh_from_db()
        assert not dish.is_available

    def test_cook_returns_dish_from_stop_list(self, client_for):
        dish = DishFactory(is_available=False)

        response = client_for(User.Role.COOK).patch(availability_url(dish), {"is_available": True})

        assert response.status_code == 200
        dish.refresh_from_db()
        assert dish.is_available

    def test_waiter_cannot_toggle(self, client_for):
        dish = DishFactory()

        response = client_for(User.Role.WAITER).patch(
            availability_url(dish), {"is_available": False}
        )

        assert response.status_code == 403

    @pytest.mark.parametrize("fmt", ["json", "multipart"])
    def test_empty_request_does_not_hide_dish(self, client_for, fmt):
        dish = DishFactory()

        response = client_for(User.Role.COOK).patch(availability_url(dish), {}, format=fmt)

        assert response.status_code == 400
        dish.refresh_from_db()
        assert dish.is_available


class TestCategories:
    def test_guest_does_not_see_inactive(self, api_client):
        active = CategoryFactory()
        CategoryFactory(is_active=False)

        response = api_client.get(CATEGORIES_URL)

        assert [c["slug"] for c in response.data] == [active.slug]

    def test_manager_sees_inactive(self, client_for):
        CategoryFactory()
        CategoryFactory(is_active=False)

        assert len(client_for(User.Role.MANAGER).get(CATEGORIES_URL).data) == 2

    def test_cannot_delete_category_with_dishes(self, client_for):
        dish = DishFactory()
        url = reverse("menu-api:category-detail", kwargs={"slug": dish.category.slug})

        response = client_for(User.Role.MANAGER).delete(url)

        assert response.status_code == 409
        assert Category.objects.filter(pk=dish.category.pk).exists()

    def test_delete_empty_category(self, client_for):
        category = CategoryFactory()
        url = reverse("menu-api:category-detail", kwargs={"slug": category.slug})

        assert client_for(User.Role.MANAGER).delete(url).status_code == 204


def test_dish_detail_by_slug(api_client):
    dish = DishFactory(slug="plov")

    response = api_client.get(dish_url(dish))

    assert response.status_code == 200
    assert response.data["category_name"] == dish.category.name
