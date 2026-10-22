import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.tasks import delay_on_commit
from apps.notifications.tasks import notify_new_reservation
from apps.reservations.models import Reservation
from apps.reservations.rules import DURATION, REMINDER_BEFORE, ReservationError, validate_start
from apps.tables.models import Table

logger = logging.getLogger(__name__)


def reservation_create(
    *,
    start_at: datetime,
    guests_count: int,
    guest_name: str,
    phone: str,
    email: str = "",
    comment: str = "",
    user=None,
) -> Reservation:
    """Бронирует самый маленький свободный стол, куда помещаются гости.

    Защита от двойной брони:
    1. select_for_update блокирует подходящие столы до конца транзакции.
       Второй параллельный запрос ждёт и после разблокировки уже видит
       первую бронь, поэтому выберет другой стол или получит отказ.
    2. ExclusionConstraint в PostgreSQL (миграция 0002) — страховка на уровне БД.
    """
    validate_start(start_at)
    end_at = start_at + DURATION

    with transaction.atomic():
        # Сначала маленькие столы: не отдаём VIP на 10 мест паре гостей
        tables = list(
            Table.objects.select_for_update()
            .filter(is_active=True, capacity__gte=guests_count)
            .order_by("capacity", "number")
        )
        if not tables:
            raise ReservationError(
                "У нас нет стола на столько гостей. Позвоните нам, и мы что-нибудь придумаем.",
                "too_many_guests",
            )

        busy_ids = set(
            Reservation.objects.active()
            .filter(table__in=tables)
            .overlapping(start_at, end_at)
            .values_list("table_id", flat=True)
        )
        table = next((table for table in tables if table.pk not in busy_ids), None)
        if table is None:
            raise ReservationError(
                "На это время все подходящие столы заняты. Выберите другое время.",
                "no_tables",
            )

        reservation = Reservation.objects.create(
            user=user,
            table=table,
            guest_name=guest_name,
            phone=phone,
            email=email,
            comment=comment,
            guests_count=guests_count,
            start_at=start_at,
            end_at=end_at,
        )
        delay_on_commit(notify_new_reservation, reservation.pk)

    logger.info("Бронь %s: стол №%s на %s", reservation.pk, table.number, start_at.isoformat())
    return reservation


def reservation_cancel(*, reservation: Reservation) -> Reservation:
    if reservation.status != Reservation.Status.CONFIRMED:
        raise ReservationError("Эта бронь уже не активна.", "not_active")
    if reservation.start_at <= timezone.now():
        raise ReservationError("Время брони уже наступило, её нельзя отменить.", "already_started")

    reservation.status = Reservation.Status.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.save(update_fields=["status", "cancelled_at"])
    logger.info("Бронь %s отменена", reservation.pk)
    return reservation


# Какие статусы официант или менеджер может поставить вручную
STAFF_STATUSES = (Reservation.Status.COMPLETED, Reservation.Status.NO_SHOW)


def reservation_set_status(*, reservation: Reservation, status: str) -> Reservation:
    """Отметка о визите: гость пришёл или не пришёл."""
    if status not in STAFF_STATUSES:
        raise ReservationError("Недопустимый статус.", "invalid_status")
    if reservation.status != Reservation.Status.CONFIRMED:
        raise ReservationError("Эта бронь уже не активна.", "not_active")
    if status == Reservation.Status.NO_SHOW and reservation.start_at > timezone.now():
        raise ReservationError(
            "Отметить «не пришёл» можно только после времени брони.", "too_early"
        )

    reservation.status = status
    reservation.save(update_fields=["status"])
    return reservation


def reservation_send_due_reminders(*, now: datetime | None = None) -> int:
    """Письмо-напоминание гостям, у которых бронь в ближайшие 2 часа.

    Каждая бронь обрабатывается в своей транзакции: если письмо одному гостю
    не ушло, остальные всё равно получат свои, а неудачное повторится
    при следующем запуске. reminder_sent_at не даёт отправить письмо дважды,
    а skip_locked — двум воркерам взять одну бронь одновременно.
    """
    now = now or timezone.now()
    due_ids = list(
        Reservation.objects.active()
        .filter(
            reminder_sent_at__isnull=True,
            start_at__gt=now,
            start_at__lte=now + REMINDER_BEFORE,
        )
        .exclude(email="")
        .values_list("pk", flat=True)
    )

    sent = 0
    for reservation_id in due_ids:
        try:
            with transaction.atomic():
                reservation = (
                    Reservation.objects.select_for_update(skip_locked=True)
                    .select_related("table")
                    .filter(pk=reservation_id, reminder_sent_at__isnull=True)
                    .first()
                )
                if reservation is None:
                    continue
                _send_reminder_email(reservation)
                reservation.reminder_sent_at = now
                reservation.save(update_fields=["reminder_sent_at"])
                sent += 1
        except Exception:
            logger.exception("Не удалось отправить напоминание о брони %s", reservation_id)
    return sent


def _send_reminder_email(reservation: Reservation) -> None:
    start = timezone.localtime(reservation.start_at)
    link = settings.SITE_URL.rstrip("/") + reverse(
        "reservations:detail", kwargs={"token": reservation.token}
    )
    send_mail(
        subject="Напоминание о брони в чайхане Bahor",
        message=(
            f"Здравствуйте, {reservation.guest_name}!\n\n"
            f"Ждём вас сегодня в {start:%H:%M}. Стол №{reservation.table.number}, "
            f"гостей: {reservation.guests_count}.\n\n"
            f"Если планы изменились, отмените бронь по ссылке:\n{link}\n"
        ),
        from_email=None,
        recipient_list=[reservation.email],
    )
