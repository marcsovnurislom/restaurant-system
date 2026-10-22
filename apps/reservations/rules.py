"""Правила бронирования: часы работы, длительность, сетка слотов.

Чистые функции без запросов к БД — легко тестировать с любым «сейчас».
"""

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.core.errors import DomainError

DURATION = timedelta(hours=2)
SLOT_STEP = timedelta(minutes=30)
OPENS_AT = time(10, 0)
CLOSES_AT = time(23, 0)
MIN_LEAD_TIME = timedelta(minutes=30)
MAX_DAYS_AHEAD = 30
REMINDER_BEFORE = timedelta(hours=2)


class ReservationError(DomainError):
    # Нет свободных столов — 409: запрос верный, но мест нет
    conflict_codes = frozenset({"no_tables"})


def slot_times() -> list[time]:
    """Время начала броней: 10:00, 10:30, ..., 21:00 (бронь должна закончиться к закрытию)."""
    day = date(2000, 1, 1)
    current = datetime.combine(day, OPENS_AT)
    last = datetime.combine(day, CLOSES_AT) - DURATION
    times = []
    while current <= last:
        times.append(current.time())
        current += SLOT_STEP
    return times


def day_slots(day: date) -> list[datetime]:
    tz = timezone.get_current_timezone()
    return [timezone.make_aware(datetime.combine(day, slot), tz) for slot in slot_times()]


def is_within_booking_window(start_at: datetime, *, now: datetime) -> bool:
    return now + MIN_LEAD_TIME <= start_at <= now + timedelta(days=MAX_DAYS_AHEAD)


def validate_start(start_at: datetime, *, now: datetime | None = None) -> None:
    now = now or timezone.now()
    local = timezone.localtime(start_at)

    # time() учитывает секунды, поэтому 19:00:15 тоже не пройдёт проверку
    if local.time() not in slot_times():
        first, last = slot_times()[0], slot_times()[-1]
        raise ReservationError(
            f"Бронь возможна с {first:%H:%M} до {last:%H:%M}, начало каждые 30 минут.",
            "invalid_slot",
        )
    if start_at < now + MIN_LEAD_TIME:
        raise ReservationError("Бронь нужно сделать минимум за 30 минут.", "too_soon")
    if start_at > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ReservationError(
            f"Бронь доступна не дальше чем на {MAX_DAYS_AHEAD} дней вперёд.", "too_far"
        )
