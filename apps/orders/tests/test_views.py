"""Корзина и заказ на сайте."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.payments.models import Payment
from apps.tables.tests.factories import TableFactory

pytestmark = pytest.mark.django_db

CART_URL = reverse("orders:cart")
CHECKOUT_URL = reverse("orders:checkout")


def add_to_cart(client, dish, quantity=1, next_url=""):
    return client.post(
        reverse("orders:cart-add", kwargs={"slug": dish.slug}),
        {"quantity": quantity, "next": next_url},
    )


@pytest.fixture
def checkout_data():
    return {
        "type": "pickup",
        "customer_name": "Нодира",
        "phone": "+998935554433",
        "payment_method": "cash",
    }


class TestCart:
    def test_add_returns_to_page(self, client):
        dish = DishFactory()

        response = add_to_cart(client, dish, next_url="/menu/#supy")

        assert response.url == "/menu/#supy"
        assert client.session["cart"] == {str(dish.pk): 1}

    def test_no_open_redirect(self, client):
        response = add_to_cart(client, DishFactory(), next_url="https://evil.example/")

        assert response.url == CART_URL

    def test_cannot_add_stop_listed(self, client):
        assert add_to_cart(client, DishFactory(is_available=False)).status_code == 404

    def test_cart_page_and_badge(self, client):
        add_to_cart(client, DishFactory(name="Самса", price=Decimal("12000")), quantity=3)

        html = client.get(CART_URL).content.decode()

        assert "Самса" in html
        assert "36 000 сум" in html
        assert '<span class="badge">3</span>' in html

    def test_update_to_zero_removes(self, client):
        dish = DishFactory()
        add_to_cart(client, dish)

        client.post(reverse("orders:cart-update", kwargs={"slug": dish.slug}), {"quantity": 0})

        assert client.session["cart"] == {}

    def test_dine_in_only_from_table(self, client):
        add_to_cart(client, DishFactory())
        assert "dine_in" not in client.get(CART_URL).content.decode()

        client.get(TableFactory().get_absolute_url())

        assert 'value="dine_in"' in client.get(CART_URL).content.decode()


class TestCheckout:
    def test_cash_pickup(self, client, checkout_data):
        add_to_cart(client, DishFactory(price=Decimal("30000")), quantity=2)

        response = client.post(CHECKOUT_URL, checkout_data, follow=True)

        order = Order.objects.get()
        assert order.total == Decimal("60000")
        assert response.redirect_chain[-1][0] == reverse(
            "orders:detail", kwargs={"token": order.token}
        )
        assert "Заказ принят" in response.content.decode()
        assert client.session["cart"] == {}

    def test_delivery_needs_address(self, client, checkout_data):
        add_to_cart(client, DishFactory())

        response = client.post(CHECKOUT_URL, {**checkout_data, "type": "delivery"})

        assert response.context["form"].errors["address"]
        assert not Order.objects.exists()

    def test_dish_ran_out_while_in_cart(self, client, checkout_data):
        dish = DishFactory(name="Шурпа")
        add_to_cart(client, dish)
        add_to_cart(client, DishFactory(name="Самса"))
        dish.is_available = False
        dish.save()

        response = client.post(CHECKOUT_URL, checkout_data, follow=True)

        html = response.content.decode()
        assert response.redirect_chain[-1][0] == CART_URL
        assert "закончились и убраны из корзины: Шурпа" in html
        assert "Самса" in html
        assert not Order.objects.exists()

    def test_cart_page_explains_removed_dish(self, client):
        dish = DishFactory(name="Шурпа")
        add_to_cart(client, dish)
        dish.is_available = False
        dish.save()

        html = client.get(CART_URL).content.decode()

        assert "закончились и убраны из корзины: Шурпа" in html
        assert client.session["cart"] == {}

    def test_dine_in_at_table(self, client, checkout_data):
        table = TableFactory(number=4)
        client.get(table.get_absolute_url())
        add_to_cart(client, DishFactory())

        client.post(CHECKOUT_URL, {**checkout_data, "type": "dine_in"})

        assert Order.objects.get().table == table

    def test_online_payment_flow(self, client, checkout_data):
        add_to_cart(client, DishFactory(price=Decimal("40000")))

        response = client.post(CHECKOUT_URL, {**checkout_data, "payment_method": "online"})

        payment = Payment.objects.get()
        assert response.url == reverse(
            "payments:fake-checkout", kwargs={"external_id": payment.external_id}
        )

        page = client.post(response.url, {"action": "pay"}, follow=True)

        order = Order.objects.get()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED
        assert "Оплата прошла" in page.content.decode()

    def test_online_payment_declined(self, client, checkout_data):
        add_to_cart(client, DishFactory())
        response = client.post(CHECKOUT_URL, {**checkout_data, "payment_method": "online"})

        page = client.post(response.url, {"action": "fail"}, follow=True)

        order = Order.objects.get()
        assert order.payment_status == Order.PaymentStatus.UNPAID
        assert "Оплатить" in page.content.decode()


class TestOrderPage:
    def test_shows_items_and_cancel(self, client):
        order = make_order(dishes=[DishFactory(name="Манты")])

        html = client.get(reverse("orders:detail", kwargs={"token": order.token})).content.decode()

        assert "Манты × 1" in html
        assert "Отменить заказ" in html

    def test_cancel(self, client):
        order = make_order()

        client.post(reverse("orders:cancel", kwargs={"token": order.token}))

        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED

    def test_pay_cash_order_shows_error(self, client):
        order = make_order()

        response = client.post(reverse("orders:pay", kwargs={"token": order.token}), follow=True)

        assert "оплачивается при получении" in response.content.decode()
