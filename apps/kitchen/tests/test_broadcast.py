import pytest
from django.db import transaction

from apps.kitchen import broadcast
from apps.kitchen.broadcast import KITCHEN_GROUP, notify_order_changed, order_group
from apps.orders.models import Order
from apps.orders.services import order_transition
from apps.orders.tests.factories import make_order
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class RecordingLayer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def group_send(self, group: str, message: dict) -> None:
        self.sent.append((group, message))


@pytest.fixture
def layer(monkeypatch) -> RecordingLayer:
    recording = RecordingLayer()
    monkeypatch.setattr(broadcast, "get_channel_layer", lambda: recording)
    return recording


def test_new_order_is_broadcast_after_commit(layer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order()

    assert [group for group, _ in layer.sent] == [KITCHEN_GROUP, order_group(order.token)]
    assert layer.sent[0][1]["order"]["status"] == "new"


def test_status_change_is_broadcast(layer, django_capture_on_commit_callbacks):
    order = make_order()

    with django_capture_on_commit_callbacks(execute=True):
        order_transition(
            order=order,
            to_status=Order.Status.CONFIRMED,
            by_user=UserFactory(role=User.Role.MANAGER),
        )

    kitchen_message = layer.sent[0][1]
    guest_message = layer.sent[1][1]
    assert kitchen_message["type"] == "order.updated"
    assert kitchen_message["order"]["status"] == "confirmed"
    assert guest_message["order"]["status_display"] == "Подтверждён"


def test_nothing_is_sent_if_transaction_rolls_back(layer, django_capture_on_commit_callbacks):
    order = make_order()

    with (
        django_capture_on_commit_callbacks(execute=True) as callbacks,
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        notify_order_changed(order.pk)
        raise RuntimeError

    assert callbacks == []
    assert layer.sent == []


def test_broken_channel_layer_does_not_break_order(
    monkeypatch, django_capture_on_commit_callbacks, caplog
):
    """Redis упал — заказ всё равно создаётся, ошибка только в логе.

    Этот тест поймал баг: с functools.partial обработчик ошибок Django сам падал.
    """

    class BrokenLayer:
        async def group_send(self, group, message):
            raise ConnectionError("Redis недоступен")

    monkeypatch.setattr(broadcast, "get_channel_layer", BrokenLayer)

    with django_capture_on_commit_callbacks(execute=True):
        order = make_order()

    assert Order.objects.filter(pk=order.pk).exists()
    assert "Redis недоступен" in caplog.text
