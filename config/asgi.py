"""ASGI-точка входа: обычные HTTP-запросы и WebSocket (Django Channels)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Django нужно инициализировать до импорта consumers: они импортируют модели
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.kitchen.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Origin проверяется по ALLOWED_HOSTS: чужой сайт не откроет сокет от имени гостя.
        # AuthMiddlewareStack достаёт пользователя из сессии, как в обычных views.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
