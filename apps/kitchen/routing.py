from django.urls import path

from apps.kitchen.consumers import KitchenConsumer, OrderStatusConsumer

websocket_urlpatterns = [
    path("ws/kitchen/", KitchenConsumer.as_asgi()),
    path("ws/orders/<uuid:token>/", OrderStatusConsumer.as_asgi()),
]
