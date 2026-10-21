import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("restaurant")
# Все настройки Celery берутся из Django settings с префиксом CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
