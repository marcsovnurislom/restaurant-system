"""WebSocket целиком: подключение, права и доставка событий через слой Channels.

transaction=True: consumer ходит в БД из другого потока (database_sync_to_async),
а обычный тест держит данные в незакоммиченной транзакции, которую тот поток не видит.
"""

import uuid

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser

from apps.kitchen.broadcast import broadcast_order
from apps.kitchen.consumers import CLOSE_FORBIDDEN, CLOSE_NOT_FOUND
from apps.kitchen.routing import websocket_urlpatterns
from apps.orders.tests.factories import make_order
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db(transaction=True)

application = URLRouter(websocket_urlpatterns)


def communicator(path: str, user=None) -> WebsocketCommunicator:
    socket = WebsocketCommunicator(application, path)
    socket.scope["user"] = user or AnonymousUser()
    return socket


def run(coroutine_function) -> None:
    async_to_sync(coroutine_function)()


class TestKitchenSocket:
    def test_staff_receives_order_updates(self):
        cook = UserFactory(role=User.Role.COOK)
        order = make_order()

        async def scenario():
            socket = communicator("/ws/kitchen/", cook)
            connected, _ = await socket.connect()
            assert connected

            await database_sync_to_async(broadcast_order)(order.pk)

            message = await socket.receive_json_from()
            assert message["type"] == "order.updated"
            assert message["order"]["id"] == order.pk
            assert message["order"]["items"]
            await socket.disconnect()

        run(scenario)

    @pytest.mark.parametrize("role", [None, User.Role.CUSTOMER])
    def test_guests_are_rejected(self, role):
        user = UserFactory(role=role) if role else None

        async def scenario():
            socket = communicator("/ws/kitchen/", user)
            connected, code = await socket.connect()
            assert not connected
            assert code == CLOSE_FORBIDDEN

        run(scenario)

    def test_incoming_messages_are_ignored(self):
        manager = UserFactory(role=User.Role.MANAGER)

        async def scenario():
            socket = communicator("/ws/kitchen/", manager)
            await socket.connect()
            await socket.send_json_to({"action": "transition", "status": "completed"})
            assert await socket.receive_nothing()
            await socket.disconnect()

        run(scenario)


class TestOrderSocket:
    def test_guest_receives_only_own_order(self):
        own, other = make_order(), make_order()

        async def scenario():
            socket = communicator(f"/ws/orders/{own.token}/")
            connected, _ = await socket.connect()
            assert connected

            await database_sync_to_async(broadcast_order)(other.pk)
            assert await socket.receive_nothing()

            await database_sync_to_async(broadcast_order)(own.pk)
            message = await socket.receive_json_from()
            assert message["order"]["status"] == "new"
            # Гостю не уходят данные для кухни
            assert "items" not in message["order"]
            await socket.disconnect()

        run(scenario)

    def test_unknown_token_is_rejected(self):
        async def scenario():
            socket = communicator(f"/ws/orders/{uuid.uuid4()}/")
            connected, code = await socket.connect()
            assert not connected
            assert code == CLOSE_NOT_FOUND

        run(scenario)
