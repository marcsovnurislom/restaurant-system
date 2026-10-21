import uuid
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.tables.tests.factories import TableFactory
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("orders-api:order-list")
MY_URL = reverse("orders-api:order-my")


def url(order: Order, action: str = "detail") -> str:
    return reverse(f"orders-api:order-{action}", kwargs={"pk": order.pk})


def client_as(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def plov():
    return DishFactory(slug="plov", price=Decimal("55000"))


@pytest.fixture
def payload(plov):
    return {
        "type": "pickup",
        "items": [{"dish": "plov", "quantity": 2}],
        "customer_name": "Азиз",
        "phone": "+998901234567",
        "payment_method": "cash",
    }


class TestCreate:
    def test_guest_creates_order(self, api_client, payload):
        response = api_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 201
        assert response.data["total"] == "110000.00"
        assert response.data["items"][0]["line_total"] == "110000.00"
        assert response.data["next_statuses"] == ["confirmed", "cancelled"]

    def test_client_price_is_ignored(self, api_client, payload):
        payload["items"][0]["price"] = "1"
        payload["total"] = "1"

        response = api_client.post(LIST_URL, payload, format="json")

        assert response.data["total"] == "110000.00"

    def test_unknown_dish(self, api_client, payload):
        payload["items"] = [{"dish": "net-takogo", "quantity": 1}]

        assert api_client.post(LIST_URL, payload, format="json").status_code == 400

    def test_stop_listed_dish_is_conflict(self, api_client, payload, plov):
        plov.is_available = False
        plov.save()

        response = api_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 409

    def test_delivery_without_address(self, api_client, payload):
        response = api_client.post(LIST_URL, {**payload, "type": "delivery"}, format="json")

        assert response.status_code == 400

    def test_dine_in_by_table_token(self, api_client, payload):
        table = TableFactory(number=7)

        response = api_client.post(
            LIST_URL,
            {**payload, "type": "dine_in", "table_token": str(table.qr_token)},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["table_number"] == 7

    def test_unknown_table_token(self, api_client, payload):
        response = api_client.post(
            LIST_URL,
            {**payload, "type": "dine_in", "table_token": str(uuid.uuid4())},
            format="json",
        )

        assert response.status_code == 400
        assert "table_token" in response.data

    def test_logged_in_user_sees_order_in_my(self, payload):
        client = client_as(UserFactory())
        client.post(LIST_URL, payload, format="json")

        assert client.get(MY_URL).data["count"] == 1


class TestStaff:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [(User.Role.COOK, 200), (User.Role.COURIER, 200), (User.Role.CUSTOMER, 403)],
    )
    def test_list_permissions(self, client_for, role, expected):
        assert client_for(role).get(LIST_URL).status_code == expected

    def test_list_query_count_is_constant(self, client_for, django_assert_num_queries):
        client = client_for(User.Role.MANAGER)
        for _ in range(5):
            make_order(dishes=DishFactory.create_batch(3))

        # COUNT + заказы со столами + позиции + история
        with django_assert_num_queries(4):
            response = client.get(LIST_URL)

        assert response.data["count"] == 5

    def test_filter_by_status(self, client_for):
        make_order()
        cancelled = make_order()
        Order.objects.filter(pk=cancelled.pk).update(status=Order.Status.CANCELLED)

        response = client_for(User.Role.MANAGER).get(LIST_URL, {"status": "cancelled"})

        assert [item["id"] for item in response.data["results"]] == [cancelled.pk]

    def test_cook_starts_cooking(self, client_for):
        order = make_order()
        client_for(User.Role.MANAGER).post(url(order, "transition"), {"status": "confirmed"})

        response = client_for(User.Role.COOK).post(url(order, "transition"), {"status": "cooking"})

        assert response.status_code == 200
        assert response.data["status"] == "cooking"
        assert len(response.data["history"]) == 3

    def test_wrong_role_is_403(self, client_for):
        response = client_for(User.Role.COOK).post(
            url(make_order(), "transition"), {"status": "confirmed"}
        )

        assert response.status_code == 403

    def test_invalid_transition_is_400(self, client_for):
        response = client_for(User.Role.MANAGER).post(
            url(make_order(), "transition"), {"status": "completed"}
        )

        assert response.status_code == 400

    def test_customer_cannot_transition(self):
        owner = UserFactory()
        order = make_order(user=owner)

        response = client_as(owner).post(url(order, "transition"), {"status": "confirmed"})

        assert response.status_code == 403


class TestOwner:
    def test_owner_cancels(self):
        owner = UserFactory()
        order = make_order(user=owner)

        response = client_as(owner).post(url(order, "cancel"))

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_other_user_gets_404(self):
        order = make_order(user=UserFactory())

        assert client_as(UserFactory()).get(url(order)).status_code == 404
        assert client_as(UserFactory()).post(url(order, "cancel")).status_code == 404

    def test_staff_cannot_use_customer_cancel(self, client_for):
        order = make_order(user=UserFactory())

        response = client_for(User.Role.MANAGER).post(url(order, "cancel"))

        assert response.status_code == 404


class TestByToken:
    def test_view_and_cancel(self, api_client):
        order = make_order()

        detail = api_client.get(reverse("orders-api:by-token", kwargs={"token": order.token}))
        cancel = api_client.post(
            reverse("orders-api:by-token-cancel", kwargs={"token": order.token})
        )

        assert detail.status_code == 200
        assert cancel.data["status"] == "cancelled"

    def test_unknown_token(self, api_client):
        response = api_client.get(reverse("orders-api:by-token", kwargs={"token": uuid.uuid4()}))

        assert response.status_code == 404
