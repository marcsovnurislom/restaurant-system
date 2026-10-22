"""Отправка сообщений менеджеру через Telegram Bot API.

Без сторонних библиотек: один POST-запрос, urllib хватает.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 10


class TelegramError(Exception):
    """Временная ошибка (сеть, 5xx, лимиты): задачу стоит повторить позже."""


def send_telegram_message(text: str) -> bool:
    """Отправляет HTML-сообщение в чат менеджера.

    Возвращает False, если бот не настроен: в разработке это нормально,
    сообщение просто пишется в лог.
    """
    token, chat_id = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        logger.info("Telegram не настроен, сообщение:\n%s", text)
        return False

    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    ).encode()
    request = urllib.request.Request(  # noqa: S310 — адрес фиксированный, https
        API_URL.format(token=token),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):  # noqa: S310
            return True
    except urllib.error.HTTPError as exc:
        # 4xx (кроме 429) — ошибка в данных или настройках: повтор не поможет
        if 400 <= exc.code < 500 and exc.code != 429:
            logger.error("Telegram отклонил сообщение: HTTP %s", exc.code)
            return False
        raise TelegramError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TelegramError(str(exc)) from exc
