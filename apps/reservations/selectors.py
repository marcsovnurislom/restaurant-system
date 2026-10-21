from datetime import date, datetime

from django.db.models import QuerySet
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.rules import DURATION, day_slots, is_within_booking_window
from apps.tables.models import Table


def available_slots(*, day: date, guests_count: int, now: datetime | None = None) -> list[datetime]:
    """Время, на которое есть хотя бы один свободный стол нужной вместимости.

    Два запроса на весь день (столы + брони), остальное считается в Python:
    слотов всего 23, столов — десятки, это дешевле, чем запрос на каждый слот.
    """
    now = now or timezone.now()
    slots = [slot for slot in day_slots(day) if is_within_booking_window(slot, now=now)]
    if not slots:
        return []

    table_ids = set(
        Table.objects.filter(is_active=True, capacity__gte=guests_count).values_list(
            "id", flat=True
        )
    )
    if not table_ids:
        return []

    busy = list(
        Reservation.objects.active()
        .filter(table_id__in=table_ids)
        .overlapping(slots[0], slots[-1] + DURATION)
        .values_list("table_id", "start_at", "end_at")
    )

    result = []
    for slot in slots:
        slot_end = slot + DURATION
        busy_tables = {table_id for table_id, start, end in busy if start < slot_end and end > slot}
        if busy_tables != table_ids:
            result.append(slot)
    return result


def reservation_list_for(user) -> QuerySet[Reservation]:
    """Персонал видит все брони, гость — только свои."""
    reservations = Reservation.objects.select_related("table")
    if not user.is_authenticated:
        return reservations.none()
    if user.is_staff_member:
        return reservations
    return reservations.filter(user=user)
