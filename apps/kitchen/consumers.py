"""WebSocket-обработчики. Сокеты только присылают обновления, а действия
(сменить статус) идут обычными HTTP-запросами в API: там уже есть проверка прав,
CSRF и state machine, дублировать их в сокете незачем.
"""

from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.kitchen.broadcast import KITCHEN_GROUP, order_group
from apps.orders.models import Order

# Код закрытия «нет доступа». Коды 4000–4999 приложение выбирает само
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


class GroupConsumer(AsyncJsonWebsocketConsumer):
    """Подписка на одну группу Channels и пересылка её событий клиенту."""

    group_name: str | None = None

    async def join(self, group_name: str) -> None:
        self.group_name = group_name
        await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_updated(self, event: dict) -> None:
        await self.send_json({"type": "order.updated", "order": event["order"]})

    async def receive_json(self, content, **kwargs) -> None:
        # Сокет только для чтения: входящие сообщения игнорируем
        pass


class KitchenConsumer(GroupConsumer):
    """ws/kitchen/ — все изменения заказов. Только для персонала."""

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not (user and user.is_authenticated and user.is_staff_member):
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.join(KITCHEN_GROUP)


class OrderStatusConsumer(GroupConsumer):
    """ws/orders/<token>/ — статус одного заказа. Секретный токен заменяет вход в аккаунт."""

    async def connect(self) -> None:
        token: UUID = self.scope["url_route"]["kwargs"]["token"]
        if not await self.order_exists(token):
            await self.close(code=CLOSE_NOT_FOUND)
            return
        await self.join(order_group(token))

    @database_sync_to_async
    def order_exists(self, token: UUID) -> bool:
        return Order.objects.filter(token=token).exists()
