"""ASGI-точка входа. На этапе 5 сюда добавится роутинг WebSocket (Django Channels)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
