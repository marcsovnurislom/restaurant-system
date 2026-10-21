import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.rules import DURATION, ReservationError
from apps.reservations.services import (
    reservation_cancel,
    reservation_create,
    reservation_set_status,
)
from apps.reservations.tests.factories import ReservationFactory, future_slot
from apps.tables.tests.factories import TableFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def book(start_at=None, guests_count=2, **kwargs) -> Reservation:
    return reservation_create(
        start_at=start_at or future_slot(),
        guests_count=guests_count,
        guest_name="Азиз",
        phone="+998901234567",
        **kwargs,
    )


def error_code(func, *args, **kwargs) -> str:
    with pytest.raises(ReservationError) as exc:
        func(*args, **kwargs)
    return exc.value.code


class TestCreate:
    def test_picks_smallest_fitting_table(self):
        TableFactory(number=1, capacity=2)
        TableFactory(number=2, capacity=6)
        four = TableFactory(number=3, capacity=4)

        reservation = book(guests_count=3)

        assert reservation.table == four
        assert reservation.end_at - reservation.start_at == DURATION
        assert reservation.status == Reservation.Status.CONFIRMED

    def test_skips_busy_table(self):
        small = TableFactory(capacity=2)
        big = TableFactory(capacity=6)
        ReservationFactory(table=small, start_at=future_slot(hour=18))

        assert book(start_at=future_slot(hour=19)).table == big

    def test_back_to_back_bookings_share_table(self):
        table = TableFactory()
        ReservationFactory(table=table, start_at=future_slot(hour=17))

        assert book(start_at=future_slot(hour=19)).table == table

    def test_partial_overlap_is_rejected(self):
        table = TableFactory()
        ReservationFactory(table=table, start_at=future_slot(hour=18))

        assert error_code(book, start_at=future_slot(hour=19)) == "no_tables"

    def test_cancelled_reservation_frees_table(self):
        table = TableFactory()
        ReservationFactory(table=table, status=Reservation.Status.CANCELLED)

        assert book().table == table

    def test_inactive_tables_are_ignored(self):
        TableFactory(is_active=False)

        assert error_code(book) == "too_many_guests"

    def test_too_many_guests(self):
        TableFactory(capacity=10)

        assert error_code(book, guests_count=12) == "too_many_guests"

    def test_invalid_time_is_checked_before_db(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            assert error_code(book, start_at=future_slot(hour=23)) == "invalid_slot"

    def test_stores_user(self):
        TableFactory()
        user = UserFactory()

        assert book(user=user).user == user


class TestCancel:
    def test_cancel(self):
        reservation = reservation_cancel(reservation=ReservationFactory())

        reservation.refresh_from_db()
        assert reservation.status == Reservation.Status.CANCELLED
        assert reservation.cancelled_at is not None
        assert not reservation.is_cancellable

    def test_cannot_cancel_twice(self):
        reservation = ReservationFactory(status=Reservation.Status.CANCELLED)

        assert error_code(reservation_cancel, reservation=reservation) == "not_active"

    def test_cannot_cancel_started(self):
        reservation = ReservationFactory(start_at=timezone.now() - timedelta(minutes=10))

        assert error_code(reservation_cancel, reservation=reservation) == "already_started"


class TestSetStatus:
    def test_guest_arrived(self):
        reservation = reservation_set_status(
            reservation=ReservationFactory(), status=Reservation.Status.COMPLETED
        )

        assert reservation.status == Reservation.Status.COMPLETED

    def test_no_show_only_after_start(self):
        future = ReservationFactory()
        past = ReservationFactory(start_at=timezone.now() - timedelta(hours=1))

        assert (
            error_code(reservation_set_status, reservation=future, status="no_show") == "too_early"
        )
        assert reservation_set_status(reservation=past, status="no_show").status == "no_show"

    def test_staff_cannot_set_cancelled_or_confirmed(self):
        reservation = ReservationFactory()

        for status in ("cancelled", "confirmed"):
            assert (
                error_code(reservation_set_status, reservation=reservation, status=status)
                == "invalid_status"
            )

    def test_only_active_reservation(self):
        reservation = ReservationFactory(status=Reservation.Status.CANCELLED)

        assert (
            error_code(reservation_set_status, reservation=reservation, status="completed")
            == "not_active"
        )


# --- Только PostgreSQL ------------------------------------------------------
# SQLite не поддерживает ни SELECT ... FOR UPDATE, ни EXCLUDE-constraints.
# В CI и в Docker тесты идут на PostgreSQL, там эти проверки выполняются.

requires_postgres = pytest.mark.skipif(connection.vendor != "postgresql", reason="нужен PostgreSQL")


@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_parallel_requests_for_last_table():
    """Два гостя одновременно бронируют единственный стол: бронь получает только один."""
    TableFactory()
    start = future_slot()
    barrier = threading.Barrier(2)
    results = []

    def attempt():
        try:
            barrier.wait()
            book(start_at=start)
            results.append("ok")
        except ReservationError as exc:
            results.append(exc.code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["no_tables", "ok"]
    assert Reservation.objects.count() == 1


@requires_postgres
def test_database_rejects_overlap_even_without_service():
    first = ReservationFactory()

    with pytest.raises(IntegrityError):
        ReservationFactory(table=first.table, start_at=first.start_at + timedelta(hours=1))


@requires_postgres
def test_database_allows_overlap_with_cancelled():
    first = ReservationFactory(status=Reservation.Status.CANCELLED)

    ReservationFactory(table=first.table, start_at=first.start_at)
