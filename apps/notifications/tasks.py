from celery import shared_task

from apps.notifications.messages import new_order_text, new_reservation_text
from apps.notifications.telegram import TelegramError, send_telegram_message
from apps.orders.selectors import order_queryset
from apps.reservations.models import Reservation

# Сетевые ошибки повторяем с растущей задержкой: 1, 2, 4, 8, 16 секунд (с разбросом)
RETRY_OPTIONS = {
    "autoretry_for": (TelegramError,),
    "retry_backoff": True,
    "retry_jitter": True,
    "max_retries": 5,
}


@shared_task(**RETRY_OPTIONS)
def notify_new_order(order_id: int) -> bool:
    order = order_queryset().filter(pk=order_id).first()
    if order is None:
        return False
    return send_telegram_message(new_order_text(order))


@shared_task(**RETRY_OPTIONS)
def notify_new_reservation(reservation_id: int) -> bool:
    reservation = Reservation.objects.select_related("table").filter(pk=reservation_id).first()
    if reservation is None:
        return False
    return send_telegram_message(new_reservation_text(reservation))
