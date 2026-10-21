from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.selectors import available_slots, reservation_list_for
from apps.reservations.tests.factories import ReservationFactory, future_slot
from apps.tables.tests.factories import TableFactory
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

DAY = timezone.localdate() + timedelta(days=2)


def hhmm(slots) -> list[str]:
    return [f"{timezone.localtime(slot):%H:%M}" for slot in slots]


def test_all_slots_free():
    TableFactory()

    assert len(available_slots(day=DAY, guests_count=2)) == 23


def test_busy_table_blocks_overlapping_slots():
    table = TableFactory()
    ReservationFactory(table=table, start_at=future_slot(hour=19))

    slots = hhmm(available_slots(day=DAY, guests_count=2))

    # Бронь 19:00–21:00 закрывает старты с 17:30 до 20:30 включительно
    assert "17:00" in slots
    assert "21:00" in slots
    for blocked in ("17:30", "18:00", "19:00", "20:30"):
        assert blocked not in slots
    assert len(slots) == 23 - 7


def test_slot_free_while_any_table_free():
    first, _second = TableFactory(), TableFactory()
    ReservationFactory(table=first, start_at=future_slot(hour=19))

    assert len(available_slots(day=DAY, guests_count=2)) == 23


def test_cancelled_reservation_does_not_block():
    ReservationFactory(table=TableFactory(), status=Reservation.Status.CANCELLED)

    assert len(available_slots(day=DAY, guests_count=2)) == 23


def test_no_table_for_big_company():
    TableFactory(capacity=4)

    assert available_slots(day=DAY, guests_count=5) == []


def test_today_hides_past_and_too_soon_slots():
    TableFactory()
    now = timezone.make_aware(datetime.combine(DAY, time(15, 10)))

    slots = hhmm(available_slots(day=DAY, guests_count=2, now=now))

    # 15:10 + 30 минут минимум = 15:40, ближайший слот — 16:00
    assert slots[0] == "16:00"


def test_two_queries_for_whole_day(django_assert_num_queries):
    tables = TableFactory.create_batch(5)
    for hour, table in zip(range(10, 20, 2), tables, strict=True):
        ReservationFactory(table=table, start_at=future_slot(hour=hour))

    with django_assert_num_queries(2):
        available_slots(day=DAY, guests_count=2)


def test_list_for_guest_and_staff():
    guest = UserFactory()
    own = ReservationFactory(user=guest)
    ReservationFactory()

    assert list(reservation_list_for(guest)) == [own]
    assert reservation_list_for(UserFactory(role=User.Role.WAITER)).count() == 2
