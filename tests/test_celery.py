"""Расписание Celery Beat ссылается на существующие задачи.

Опечатка в имени задачи не видна до продакшена: beat молча ставит в очередь
задачу, которую ни один воркер не знает. Этот тест ловит её сразу.
"""

import pytest
from django.conf import settings

from config.celery import app


@pytest.mark.parametrize("entry", sorted(settings.CELERY_BEAT_SCHEDULE))
def test_beat_schedule_tasks_exist(entry):
    app.loader.import_default_modules()

    assert settings.CELERY_BEAT_SCHEDULE[entry]["task"] in app.tasks
