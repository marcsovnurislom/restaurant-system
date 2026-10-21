from decimal import Decimal

import pytest

from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.rules import OrderError
from apps.orders.services import (
    order_cancel_by_customer,
    order_create,
    order_mark_paid,
    order_transition,
)
from apps.orders.tests.factories import make_order
from apps.tables.tests.factories import TableFactory
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

Status = Order.Status


def error_code(func, **kwargs) -> str:
    with pytest.raises(OrderError) as exc:
        func(**kwargs)
    return exc.value.code


def staff(role: str) -> User:
    return UserFactory(role=role)


class TestCreate:
    def test_pickup_order(self):
        plov = DishFactory(name="Плов", price=Decimal("55000"))
        samsa = DishFactory(name="Самса", price=Decimal("12000"))
        user = UserFactory()

        order = order_create(
            items=[(plov.pk, 1), (samsa.pk, 3)],
            order_type=Order.Type.PICKUP,
            customer_name="Азиз",
            phone="+998901234567",
            payment_method=Order.PaymentMethod.CASH,
            user=user,
        )

        assert order.items_total == Decimal("91000")
        assert order.delivery_fee == 0
        assert order.total == Decimal("91000")
        assert order.user == user
        assert order.status == Status.NEW
        assert sorted(order.items.values_list("dish_name", "quantity")) == [
            ("Плов", 1),
            ("Самса", 3),
        ]
        assert list(order.history.values_list("from_status", "to_status")) == [("", "new")]

    def test_same_dish_twice_is_merged(self):
        dish = DishFactory()

        order = make_order(dishes=[dish, dish])

        assert order.items.get().quantity == 2

    def test_price_is_snapshot(self):
        dish = DishFactory(price=Decimal("30000"))
        order = make_order(dishes=[dish])

        dish.price = Decimal("99000")
        dish.save()

        assert order.items.get().unit_price == Decimal("30000")

    def test_delivery_fee_below_threshold(self):
        order = make_order(
            dishes=[DishFactory(price=Decimal("60000"))],
            order_type=Order.Type.DELIVERY,
            address="ул. Навои, 1",
        )

        assert order.delivery_fee == Decimal("15000")
        assert order.total == Decimal("75000")

    def test_free_delivery(self):
        order = make_order(
            dishes=[DishFactory(price=Decimal("160000"))],
            order_type=Order.Type.DELIVERY,
            address="ул. Навои, 1",
        )

        assert order.delivery_fee == 0

    def test_min_delivery_order(self):
        assert (
            error_code(
                make_order,
                dishes=[DishFactory(price=Decimal("20000"))],
                order_type=Order.Type.DELIVERY,
                address="ул. Навои, 1",
            )
            == "min_order"
        )

    def test_delivery_requires_address(self):
        assert (
            error_code(make_order, order_type=Order.Type.DELIVERY, address="   ")
            == "address_required"
        )

    def test_dine_in_requires_table(self):
        assert error_code(make_order, order_type=Order.Type.DINE_IN) == "table_required"

    def test_dine_in_with_table(self):
        table = TableFactory()

        assert make_order(order_type=Order.Type.DINE_IN, table=table).table == table

    def test_pickup_ignores_table_and_address(self):
        order = make_order(table=TableFactory(), address="ул. Навои, 1")

        assert order.table is None
        assert order.address == ""

    def test_unavailable_dish(self):
        gone = DishFactory(name="Шурпа", is_available=False)

        with pytest.raises(OrderError) as exc:
            make_order(dishes=[DishFactory(), gone])

        assert exc.value.code == "unavailable"
        assert "Шурпа" in exc.value.message
        assert not Order.objects.exists()

    def test_unknown_dish(self):
        assert (
            error_code(
                order_create,
                items=[(999999, 1)],
                order_type=Order.Type.PICKUP,
                customer_name="x",
                phone="+998901234567",
                payment_method=Order.PaymentMethod.CASH,
            )
            == "unavailable"
        )

    def test_empty(self):
        assert (
            error_code(
                order_create,
                items=[],
                order_type=Order.Type.PICKUP,
                customer_name="x",
                phone="+998901234567",
                payment_method=Order.PaymentMethod.CASH,
            )
            == "empty"
        )

    @pytest.mark.parametrize("quantity", [0, 21])
    def test_invalid_quantity(self, quantity):
        dish = DishFactory()

        assert (
            error_code(
                order_create,
                items=[(dish.pk, quantity)],
                order_type=Order.Type.PICKUP,
                customer_name="x",
                phone="+998901234567",
                payment_method=Order.PaymentMethod.CASH,
            )
            == "invalid_quantity"
        )


class TestTransitions:
    def test_full_delivery_flow(self):
        order = make_order(
            dishes=[DishFactory(price=Decimal("60000"))],
            order_type=Order.Type.DELIVERY,
            address="ул. Навои, 1",
        )
        steps = [
            (User.Role.MANAGER, Status.CONFIRMED),
            (User.Role.COOK, Status.COOKING),
            (User.Role.COOK, Status.READY),
            (User.Role.COURIER, Status.DELIVERING),
            (User.Role.COURIER, Status.COMPLETED),
        ]

        for role, status in steps:
            order = order_transition(order=order, to_status=status, by_user=staff(role))

        assert order.status == Status.COMPLETED
        assert list(order.history.values_list("to_status", flat=True)) == [
            "new",
            "confirmed",
            "cooking",
            "ready",
            "delivering",
            "completed",
        ]

    def test_pickup_completed_by_waiter(self):
        order = make_order()
        manager, cook = staff(User.Role.MANAGER), staff(User.Role.COOK)
        order_transition(order=order, to_status=Status.CONFIRMED, by_user=manager)
        order_transition(order=order, to_status=Status.COOKING, by_user=cook)
        order_transition(order=order, to_status=Status.READY, by_user=cook)

        order = order_transition(
            order=order, to_status=Status.COMPLETED, by_user=staff(User.Role.WAITER)
        )

        assert order.status == Status.COMPLETED

    def test_cannot_skip_steps(self):
        assert (
            error_code(
                order_transition,
                order=make_order(),
                to_status=Status.COOKING,
                by_user=staff(User.Role.COOK),
            )
            == "invalid_transition"
        )

    def test_unknown_status(self):
        assert (
            error_code(
                order_transition,
                order=make_order(),
                to_status="eaten",
                by_user=staff(User.Role.MANAGER),
            )
            == "invalid_transition"
        )

    def test_wrong_role(self):
        assert (
            error_code(
                order_transition,
                order=make_order(),
                to_status=Status.CONFIRMED,
                by_user=staff(User.Role.COOK),
            )
            == "forbidden"
        )

    def test_admin_can_do_anything_allowed(self):
        order = order_transition(
            order=make_order(), to_status=Status.CONFIRMED, by_user=staff(User.Role.ADMIN)
        )

        assert order.status == Status.CONFIRMED

    def test_pickup_cannot_go_to_courier(self):
        order = make_order()
        Order.objects.filter(pk=order.pk).update(status=Status.READY)

        assert (
            error_code(
                order_transition,
                order=order,
                to_status=Status.DELIVERING,
                by_user=staff(User.Role.MANAGER),
            )
            == "invalid_transition"
        )

    def test_unpaid_online_order_cannot_be_confirmed(self):
        order = make_order(payment_method=Order.PaymentMethod.ONLINE)

        assert (
            error_code(
                order_transition,
                order=order,
                to_status=Status.CONFIRMED,
                by_user=staff(User.Role.MANAGER),
            )
            == "awaiting_payment"
        )

    def test_records_who_changed(self):
        manager = staff(User.Role.MANAGER)

        order = order_transition(order=make_order(), to_status=Status.CONFIRMED, by_user=manager)

        assert order.history.last().changed_by == manager


class TestCustomerCancel:
    def test_new_order(self):
        order = order_cancel_by_customer(order=make_order())

        assert order.status == Status.CANCELLED

    def test_too_late_after_confirmation(self):
        order = order_transition(
            order=make_order(), to_status=Status.CONFIRMED, by_user=staff(User.Role.MANAGER)
        )

        assert error_code(order_cancel_by_customer, order=order) == "too_late"


class TestMarkPaid:
    def test_paid_order_is_confirmed(self):
        order = order_mark_paid(order=make_order(payment_method=Order.PaymentMethod.ONLINE))

        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Status.CONFIRMED
        assert order.history.last().changed_by is None

    def test_idempotent(self):
        order = make_order(payment_method=Order.PaymentMethod.ONLINE)
        order_mark_paid(order=order)

        order_mark_paid(order=order)

        assert order.history.count() == 2

    def test_cancelled_order_stays_cancelled(self, caplog):
        order = make_order(payment_method=Order.PaymentMethod.ONLINE)
        order_cancel_by_customer(order=order)

        order = order_mark_paid(order=order)

        assert order.status == Status.CANCELLED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert "нужен возврат" in caplog.text
