from celery import shared_task

from apps.reservations.services import reservation_send_due_reminders


@shared_task
def send_reservation_reminders() -> int:
    """Периодическая задача (Celery Beat): напоминания о брони за 2 часа."""
    return reservation_send_due_reminders()
