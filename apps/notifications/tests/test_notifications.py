"""Уведомления менеджеру уходят после коммита и только когда заказ реальный."""

from decimal import Decimal

import pytest

from apps.menu.tests.factories import DishFactory
from apps.notifications import tasks
from apps.orders.models import Order
from apps.orders.services import order_mark_paid
from apps.orders.tests.factories import make_order
from apps.reservations.services import reservation_create
from apps.reservations.tests.factories import future_slot
from apps.tables.tests.factories import TableFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def sent(monkeypatch) -> list[str]:
    messages: list[str] = []
    monkeypatch.setattr(tasks, "send_telegram_message", lambda text: messages.append(text) or True)
    return messages


def test_cash_order_notifies_manager(sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order(
            dishes=[DishFactory(name="Плов", price=Decimal("55000"))],
            customer_name="Азиз",
            comment="Без лука",
        )

    assert len(sent) == 1
    assert f"Новый заказ №{order.pk}" in sent[0]
    assert "1× Плов" in sent[0]
    assert "при получении" in sent[0]
    assert "Без лука" in sent[0]


def test_online_order_notifies_only_after_payment(sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order(payment_method=Order.PaymentMethod.ONLINE)
    assert sent == []

    with django_capture_on_commit_callbacks(execute=True):
        order_mark_paid(order=order)

    assert len(sent) == 1
    assert "оплачен онлайн" in sent[0]


def test_guest_input_is_escaped(sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        make_order(customer_name='<a href="x">Хакер</a>')

    assert "&lt;a href=&quot;x&quot;&gt;Хакер&lt;/a&gt;" in sent[0]
    assert "<a href" not in sent[0]


def test_no_notification_before_commit(sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        make_order()

    assert sent == []
    assert callbacks


def test_new_reservation_notifies_manager(sent, django_capture_on_commit_callbacks):
    TableFactory(number=5)

    with django_capture_on_commit_callbacks(execute=True):
        reservation_create(
            start_at=future_slot(hour=19),
            guests_count=3,
            guest_name="Нодира",
            phone="+998935554433",
        )

    assert len(sent) == 1
    assert "Новая бронь" in sent[0]
    assert "19:00, стол №5, гостей: 3" in sent[0]


def test_deleted_order_is_skipped(sent):
    assert tasks.notify_new_order(999999) is False
    assert sent == []
