import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.rules import DURATION, ReservationError, validate_start
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
