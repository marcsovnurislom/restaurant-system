import pytest
from django.urls import reverse

from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.users.models import User
from apps.users.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

BOARD_URL = reverse("kitchen:board")
SNAPSHOT_URL = reverse("kitchen:snapshot")


@pytest.fixture
def cook_client(client):
    client.force_login(UserFactory(role=User.Role.COOK))
    return client


def test_anonymous_is_sent_to_login(client):
    response = client.get(BOARD_URL)

    assert response.status_code == 302
    assert response.url.startswith(reverse("kitchen:login"))


def test_customer_is_forbidden(client):
    client.force_login(UserFactory(role=User.Role.CUSTOMER))

    assert client.get(BOARD_URL).status_code == 403
    assert client.get(SNAPSHOT_URL).status_code == 403


def test_board_contains_active_orders(cook_client):
    active = make_order()
    Order.objects.filter(pk=make_order().pk).update(status=Order.Status.COMPLETED)

    response = cook_client.get(BOARD_URL)

    assert response.status_code == 200
    assert [order["id"] for order in response.context["orders"]] == [active.pk]
    assert response.context["role"] == "cook"
    assert 'id="initial-orders"' in response.content.decode()


def test_snapshot(cook_client):
    order = make_order()

    data = cook_client.get(SNAPSHOT_URL).json()

    assert [item["id"] for item in data["orders"]] == [order.pk]


def test_snapshot_query_count(cook_client, django_assert_max_num_queries):
    for _ in range(5):
        make_order()

    # сессия + пользователь + заказы + позиции + история
    with django_assert_max_num_queries(5):
        cook_client.get(SNAPSHOT_URL)


def test_login_redirects_to_board(client):
    UserFactory(username="cook1", role=User.Role.COOK)

    response = client.post(
        reverse("kitchen:login"), {"username": "cook1", "password": DEFAULT_PASSWORD}
    )

    assert response.url == BOARD_URL


def test_logout(cook_client):
    response = cook_client.post(reverse("kitchen:logout"))

    assert response.url == reverse("kitchen:login")
    assert cook_client.get(BOARD_URL).status_code == 302


@pytest.mark.parametrize(("role", "visible"), [(None, False), ("customer", False), ("cook", True)])
def test_nav_link_only_for_staff(client, role, visible):
    if role:
        client.force_login(UserFactory(role=role))

    html = client.get(reverse("menu:home")).content.decode()

    assert ("Кухня" in html) is visible


def test_order_page_connects_to_own_socket(client):
    order = make_order()

    html = client.get(reverse("orders:detail", kwargs={"token": order.token})).content.decode()

    assert f'data-socket-path="/ws/orders/{order.token}/"' in html
